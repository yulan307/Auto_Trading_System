from __future__ import annotations

import json
import math
import pickle
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except ImportError:  # pragma: no cover - exercised indirectly in non-torch environments
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


DEFAULT_TRAIN_CONFIG: dict[str, Any] = {
    "seed": 7,
    "backend": "auto",
    "epochs": 40,
    "batch_size": 32,
    "learning_rate": 1e-3,
    "dropout": 0.1,
    "hidden_dims": [128, 64],
    "valid_ratio": 0.2,
    "test_ratio": 0.2,
}


@dataclass(slots=True)
class StandardScalerState:
    mean_: list[float]
    scale_: list[float]
    feature_columns: list[str]

    def transform(self, values: np.ndarray) -> np.ndarray:
        mean = np.asarray(self.mean_, dtype=float)
        scale = np.asarray(self.scale_, dtype=float)
        return (values - mean) / scale

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fit_standard_scaler(values: np.ndarray, feature_columns: list[str]) -> StandardScalerState:
    mean = np.nanmean(values, axis=0)
    scale = np.nanstd(values, axis=0)
    scale = np.where(scale == 0, 1.0, scale)
    return StandardScalerState(mean_=mean.tolist(), scale_=scale.tolist(), feature_columns=feature_columns)


def _merge_config(config: dict | None) -> dict[str, Any]:
    merged = dict(DEFAULT_TRAIN_CONFIG)
    if config:
        merged.update(config)
    return merged


def _split_indices(row_count: int, valid_ratio: float, test_ratio: float, seed: int) -> dict[str, np.ndarray]:
    if row_count <= 1:
        return {
            "train": np.arange(row_count, dtype=int),
            "valid": np.asarray([], dtype=int),
            "test": np.asarray([], dtype=int),
        }

    rng = np.random.default_rng(seed)
    permutation = rng.permutation(row_count)
    test_count = int(row_count * test_ratio)
    valid_count = int(row_count * valid_ratio)
    if row_count >= 3:
        test_count = max(test_count, 1)
        valid_count = max(valid_count, 1)
    if test_count + valid_count >= row_count:
        test_count = 1 if row_count >= 3 else 0
        valid_count = 1 if row_count >= 3 else 0

    test_idx = permutation[:test_count]
    valid_idx = permutation[test_count : test_count + valid_count]
    train_idx = permutation[test_count + valid_count :]
    if len(train_idx) == 0:
        train_idx = permutation[: max(row_count - 2, 1)]
        valid_idx = permutation[len(train_idx) : len(train_idx) + min(1, row_count - len(train_idx))]
        test_idx = permutation[len(train_idx) + len(valid_idx) :]
    return {"train": train_idx, "valid": valid_idx, "test": test_idx}


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(math.sqrt(np.mean(np.square(y_pred - y_true)))) if len(y_true) else float("nan")


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_pred - y_true))) if len(y_true) else float("nan")


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return float("nan")
    baseline = np.mean(y_true)
    ss_res = float(np.sum(np.square(y_true - y_pred)))
    ss_tot = float(np.sum(np.square(y_true - baseline)))
    if ss_tot == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def _build_metrics_by_split(predictions_df: pd.DataFrame, target_column: str) -> dict[str, dict[str, float]]:
    metrics: dict[str, dict[str, float]] = {}
    for split_name, split_df in predictions_df.groupby("split"):
        y_true = split_df[target_column].to_numpy(dtype=float)
        y_pred = split_df["pred_strength_pct"].to_numpy(dtype=float)
        metrics[str(split_name)] = {
            "rmse": _rmse(y_true, y_pred),
            "mae": _mae(y_true, y_pred),
            "r2": _r2(y_true, y_pred),
            "rows": float(len(split_df)),
        }
    return metrics


def _fit_numpy_linear_model(x_train: np.ndarray, y_train: np.ndarray) -> dict[str, Any]:
    design = np.concatenate([x_train, np.ones((len(x_train), 1), dtype=float)], axis=1)
    params, *_ = np.linalg.lstsq(design, y_train, rcond=None)
    return {
        "backend": "numpy_fallback",
        "weights": params[:-1].reshape(-1).tolist(),
        "bias": float(params[-1]),
    }


def _predict_numpy_linear(model_payload: dict[str, Any], values: np.ndarray) -> np.ndarray:
    weights = np.asarray(model_payload["weights"], dtype=float)
    bias = float(model_payload["bias"])
    return values @ weights + bias


if torch is not None:

    class MLPRegressor(nn.Module):
        def __init__(self, input_dim: int, hidden_dims: list[int], dropout: float) -> None:
            super().__init__()
            layers: list[nn.Module] = []
            last_dim = input_dim
            for hidden_dim in hidden_dims:
                layers.extend([nn.Linear(last_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout)])
                last_dim = hidden_dim
            layers.append(nn.Linear(last_dim, 1))
            self.network = nn.Sequential(*layers)

        def forward(self, values):  # type: ignore[override]
            return self.network(values)


def _fit_torch_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    config: dict[str, Any],
) -> dict[str, Any]:
    if torch is None or nn is None or DataLoader is None or TensorDataset is None:
        raise RuntimeError("PyTorch is not available.")

    torch.manual_seed(int(config["seed"]))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = MLPRegressor(
        input_dim=x_train.shape[1],
        hidden_dims=list(config["hidden_dims"]),
        dropout=float(config["dropout"]),
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(config["learning_rate"]))
    loss_fn = nn.MSELoss()
    dataset = TensorDataset(
        torch.tensor(x_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.float32).view(-1, 1),
    )
    loader = DataLoader(dataset, batch_size=min(int(config["batch_size"]), len(dataset)), shuffle=True)
    model.train()
    for _ in range(int(config["epochs"])):
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            loss = loss_fn(model(batch_x), batch_y)
            loss.backward()
            optimizer.step()

    model.cpu().eval()
    return {
        "backend": "torch",
        "input_dim": int(x_train.shape[1]),
        "hidden_dims": list(config["hidden_dims"]),
        "dropout": float(config["dropout"]),
        "state_dict": {key: value.detach().cpu() for key, value in model.state_dict().items()},
    }


def predict_from_model_payload(model_payload: dict[str, Any], values: np.ndarray) -> np.ndarray:
    backend = model_payload.get("backend")
    if backend == "torch":
        if torch is None:
            raise RuntimeError("PyTorch-backed model cannot be used because torch is not installed.")
        model = MLPRegressor(
            input_dim=int(model_payload["input_dim"]),
            hidden_dims=list(model_payload["hidden_dims"]),
            dropout=float(model_payload["dropout"]),
        )
        model.load_state_dict(model_payload["state_dict"])
        model.eval()
        with torch.no_grad():
            predictions = model(torch.tensor(values, dtype=torch.float32)).squeeze(-1).numpy()
        return predictions.astype(float)
    if backend == "numpy_fallback":
        return _predict_numpy_linear(model_payload, values).astype(float)
    raise ValueError(f"Unsupported model backend: {backend!r}")


def train_buy_sub_ml_model(
    df,
    feature_columns: list[str],
    target_column: str = "strength_pct",
    config: dict | None = None,
) -> dict:
    if df.empty:
        raise ValueError("Training dataframe must not be empty.")
    if not feature_columns:
        raise ValueError("feature_columns must not be empty.")

    merged_config = _merge_config(config)
    training_df = df.loc[:, ["ticker", "date", *feature_columns, target_column]].dropna().reset_index(drop=True)
    if training_df.empty:
        raise ValueError("Training dataframe became empty after dropping missing values.")

    x_all = training_df.loc[:, feature_columns].to_numpy(dtype=float)
    y_all = training_df[target_column].to_numpy(dtype=float)
    split_indices = _split_indices(
        row_count=len(training_df),
        valid_ratio=float(merged_config["valid_ratio"]),
        test_ratio=float(merged_config["test_ratio"]),
        seed=int(merged_config["seed"]),
    )
    train_idx = split_indices["train"]
    scaler = fit_standard_scaler(x_all[train_idx], feature_columns=feature_columns)
    x_scaled = scaler.transform(x_all)
    x_train = x_scaled[train_idx]
    y_train = y_all[train_idx]

    backend = str(merged_config["backend"]).lower()
    if backend == "auto":
        backend = "torch" if torch is not None else "numpy_fallback"
    if backend == "torch":
        model_payload = _fit_torch_model(x_train, y_train, merged_config)
    elif backend == "numpy_fallback":
        model_payload = _fit_numpy_linear_model(x_train, y_train)
    else:
        raise ValueError(f"Unsupported training backend: {backend!r}")

    predictions = predict_from_model_payload(model_payload, x_scaled)
    split_names = np.full(len(training_df), "train", dtype=object)
    split_names[split_indices["valid"]] = "valid"
    split_names[split_indices["test"]] = "test"
    predictions_df = training_df.loc[:, ["ticker", "date", target_column]].copy()
    predictions_df["pred_strength_pct"] = predictions
    predictions_df["split"] = split_names.tolist()

    metrics = _build_metrics_by_split(predictions_df, target_column=target_column)
    metrics["overall"] = {
        "rmse": _rmse(y_all, predictions),
        "mae": _mae(y_all, predictions),
        "r2": _r2(y_all, predictions),
        "rows": float(len(training_df)),
    }

    return {
        "model": model_payload,
        "scaler": scaler,
        "metrics": metrics,
        "predictions": predictions_df,
        "train_config": {**merged_config, "resolved_backend": backend},
        "split_counts": {
            "train_rows": int((predictions_df["split"] == "train").sum()),
            "valid_rows": int((predictions_df["split"] == "valid").sum()),
            "test_rows": int((predictions_df["split"] == "test").sum()),
        },
    }


def save_model_payload(path: str, model_payload: dict[str, Any]) -> None:
    if model_payload.get("backend") == "torch" and torch is not None:
        torch.save(model_payload, path)
        return
    with open(path, "wb") as file_handle:
        pickle.dump(model_payload, file_handle)


def load_model_payload(path: str) -> dict[str, Any]:
    if torch is not None:
        try:
            payload = torch.load(path, map_location="cpu")
            if isinstance(payload, dict) and "backend" in payload:
                return payload
        except Exception:
            pass
    with open(path, "rb") as file_handle:
        payload = pickle.load(file_handle)
    if not isinstance(payload, dict) or "backend" not in payload:
        raise ValueError("Saved model payload is invalid.")
    return payload


__all__ = [
    "DEFAULT_TRAIN_CONFIG",
    "StandardScalerState",
    "fit_standard_scaler",
    "load_model_payload",
    "predict_from_model_payload",
    "save_model_payload",
    "train_buy_sub_ml_model",
]
