from __future__ import annotations

import math
import pickle
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.ml.buy_sub_ml.feature_selector import select_hist_feature_columns

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
    "backend": "auto",
    "hidden_dims": [64, 32],
    "dropout": 0.1,
    "learning_rate": 1e-3,
    "weight_decay": 1e-5,
    "batch_size": 32,
    "max_epochs": 200,
    "patience": 20,
    "loss_function": "mse",
    "target_weight_alpha": 1.0,
    "target_weight_gamma": 2.0,
    "random_seed": 42,
}
LEGACY_CONFIG_ALIASES = {
    "seed": "random_seed",
    "epochs": "max_epochs",
}
NUMERIC_EPSILON = 1e-12
LOGIT_EPSILON = 1e-6


@dataclass(slots=True)
class StandardScalerState:
    mean_: list[float]
    scale_: list[float]
    feature_columns: list[str]

    def transform(self, values: np.ndarray) -> np.ndarray:
        mean = np.asarray(self.mean_, dtype=float)
        scale = np.asarray(self.scale_, dtype=float)
        safe_scale = np.where(scale == 0, 1.0, scale)
        return (values - mean) / safe_scale

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fit_standard_scaler(values: np.ndarray, feature_columns: list[str]) -> StandardScalerState:
    mean = np.nanmean(values, axis=0)
    scale = np.nanstd(values, axis=0)
    scale = np.where(scale == 0, 1.0, scale)
    return StandardScalerState(mean_=mean.tolist(), scale_=scale.tolist(), feature_columns=list(feature_columns))


def _merge_config(config: dict | None) -> dict[str, Any]:
    merged = dict(DEFAULT_TRAIN_CONFIG)
    if not config:
        return merged
    for key, value in config.items():
        merged[LEGACY_CONFIG_ALIASES.get(key, key)] = value
    return merged


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _compute_target_weights(values: np.ndarray, alpha: float, gamma: float) -> np.ndarray:
    clipped = np.clip(values.astype(float), 0.0, 1.0)
    return 1.0 + float(alpha) * np.power(clipped, float(gamma))


def _weighted_mse(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    alpha: float,
    gamma: float,
) -> float:
    weights = _compute_target_weights(y_true, alpha=alpha, gamma=gamma)
    loss_values = np.square(y_pred - y_true) * weights
    return float(loss_values.sum() / max(weights.sum(), NUMERIC_EPSILON))


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return float("nan")
    return float(math.sqrt(np.mean(np.square(y_pred - y_true))))


def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return float("nan")
    return float(np.mean(np.abs(y_pred - y_true)))


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) == 0:
        return float("nan")
    baseline = float(np.mean(y_true))
    ss_res = float(np.sum(np.square(y_true - y_pred)))
    ss_tot = float(np.sum(np.square(y_true - baseline)))
    if ss_tot == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def _pearson(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2:
        return float("nan")
    if float(np.std(y_true)) == 0.0 or float(np.std(y_pred)) == 0.0:
        return 0.0
    return float(np.corrcoef(y_true, y_pred)[0, 1])


def _spearman(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2:
        return float("nan")
    rank_true = pd.Series(y_true).rank(method="average").to_numpy(dtype=float)
    rank_pred = pd.Series(y_pred).rank(method="average").to_numpy(dtype=float)
    if float(np.std(rank_true)) == 0.0 or float(np.std(rank_pred)) == 0.0:
        return 0.0
    return float(np.corrcoef(rank_true, rank_pred)[0, 1])


def _top_overlap_count(y_true: np.ndarray, y_pred: np.ndarray, limit: int) -> int:
    top_n = min(int(limit), len(y_true))
    if top_n <= 0:
        return 0
    true_top = set(np.argsort(-y_true)[:top_n].tolist())
    pred_top = set(np.argsort(-y_pred)[:top_n].tolist())
    return int(len(true_top & pred_top))


def _build_fit_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "fullfit_mae": _mae(y_true, y_pred),
        "fullfit_rmse": _rmse(y_true, y_pred),
        "fullfit_r2": _r2(y_true, y_pred),
        "fullfit_pearson": _pearson(y_true, y_pred),
        "fullfit_spearman": _spearman(y_true, y_pred),
        "top5_overlap_count": float(_top_overlap_count(y_true, y_pred, 5)),
        "top10_overlap_count": float(_top_overlap_count(y_true, y_pred, 10)),
        "top20_overlap_count": float(_top_overlap_count(y_true, y_pred, 20)),
    }


def _validate_numeric_columns(df: pd.DataFrame, columns: list[str], *, label: str) -> None:
    non_numeric = [column for column in columns if not pd.api.types.is_numeric_dtype(df[column])]
    if non_numeric:
        raise ValueError(f"{label} columns must be numeric: {non_numeric}")


def _build_training_frame(
    train_df: pd.DataFrame,
    *,
    target_column: str,
    feature_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    if target_column not in train_df.columns:
        raise ValueError(f"Missing target column: {target_column!r}")

    resolved_feature_columns = feature_columns or select_hist_feature_columns(train_df)
    if not resolved_feature_columns:
        raise ValueError("feature_columns must not be empty.")

    _validate_numeric_columns(train_df, resolved_feature_columns, label="Feature")
    _validate_numeric_columns(train_df, [target_column], label="Target")

    df_model = train_df.loc[:, [*resolved_feature_columns, target_column]].dropna().copy()
    if df_model.empty:
        raise ValueError("Training dataframe became empty after dropping missing values.")
    return df_model, list(resolved_feature_columns)


if torch is not None:

    class MLPRegressor(nn.Module):
        def __init__(self, input_dim: int, hidden_dims: list[int], dropout: float) -> None:
            super().__init__()
            layers: list[nn.Module] = []
            last_dim = input_dim
            for hidden_dim in hidden_dims:
                layers.extend([nn.Linear(last_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout)])
                last_dim = hidden_dim
            layers.extend([nn.Linear(last_dim, 1), nn.Sigmoid()])
            self.network = nn.Sequential(*layers)

        def forward(self, values):  # type: ignore[override]
            return self.network(values)


def _weighted_mse_loss_torch(
    predictions,
    targets,
    *,
    alpha: float,
    gamma: float,
):
    if torch is None:
        raise RuntimeError("PyTorch is not available.")
    base_loss = torch.square(predictions.view(-1) - targets.view(-1))
    weights = 1.0 + float(alpha) * torch.pow(torch.clamp(targets.view(-1), 0.0, 1.0), float(gamma))
    return torch.sum(base_loss * weights) / torch.clamp(torch.sum(weights), min=NUMERIC_EPSILON)


def _fit_numpy_fallback_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    *,
    alpha: float,
    gamma: float,
) -> tuple[dict[str, Any], list[float], int, float]:
    weights = _compute_target_weights(y_train, alpha=alpha, gamma=gamma)
    sqrt_weights = np.sqrt(weights).reshape(-1, 1)
    design = np.concatenate([x_train, np.ones((len(x_train), 1), dtype=float)], axis=1)
    target_logits = np.log(np.clip(y_train, LOGIT_EPSILON, 1.0 - LOGIT_EPSILON) / np.clip(
        1.0 - y_train,
        LOGIT_EPSILON,
        1.0,
    ))
    weighted_design = design * sqrt_weights
    weighted_target = target_logits * sqrt_weights.reshape(-1)
    params, *_ = np.linalg.lstsq(weighted_design, weighted_target, rcond=None)
    raw_predictions = design @ params
    predictions = _sigmoid(raw_predictions)
    best_train_loss = _weighted_mse(y_train, predictions, alpha=alpha, gamma=gamma)
    return (
        {
            "backend": "numpy_fallback",
            "weights": params[:-1].reshape(-1).tolist(),
            "bias": float(params[-1]),
            "hidden_dims": [],
            "dropout": 0.0,
            "output_activation": "sigmoid",
            "input_dim": int(x_train.shape[1]),
        },
        [best_train_loss],
        1,
        best_train_loss,
    )


def _fit_torch_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    *,
    hidden_dims: list[int],
    dropout: float,
    learning_rate: float,
    weight_decay: float,
    batch_size: int,
    max_epochs: int,
    patience: int,
    target_weight_alpha: float,
    target_weight_gamma: float,
    random_seed: int,
) -> tuple[dict[str, Any], list[float], int, float]:
    if torch is None or nn is None or DataLoader is None or TensorDataset is None:
        raise RuntimeError("PyTorch is not available.")

    torch.manual_seed(int(random_seed))
    np.random.seed(int(random_seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(random_seed))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = MLPRegressor(input_dim=x_train.shape[1], hidden_dims=hidden_dims, dropout=float(dropout)).to(device)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(learning_rate),
        weight_decay=float(weight_decay),
    )

    x_tensor = torch.tensor(x_train, dtype=torch.float32)
    y_tensor = torch.tensor(y_train, dtype=torch.float32).view(-1, 1)
    dataset = TensorDataset(x_tensor, y_tensor)
    loader = DataLoader(dataset, batch_size=min(int(batch_size), len(dataset)), shuffle=True)

    best_epoch = 0
    best_train_loss = float("inf")
    train_losses: list[float] = []
    best_state_dict: dict[str, Any] | None = None
    stale_epochs = 0

    for epoch_index in range(int(max_epochs)):
        model.train()
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            predictions = model(batch_x)
            loss = _weighted_mse_loss_torch(
                predictions,
                batch_y,
                alpha=target_weight_alpha,
                gamma=target_weight_gamma,
            )
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            full_predictions = model(x_tensor.to(device))
            train_loss = float(
                _weighted_mse_loss_torch(
                    full_predictions,
                    y_tensor.to(device),
                    alpha=target_weight_alpha,
                    gamma=target_weight_gamma,
                ).detach().cpu().item()
            )
        train_losses.append(train_loss)

        if train_loss + NUMERIC_EPSILON < best_train_loss:
            best_epoch = epoch_index + 1
            best_train_loss = train_loss
            stale_epochs = 0
            best_state_dict = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        else:
            stale_epochs += 1
            if stale_epochs >= int(patience):
                break

    if best_state_dict is None:
        best_state_dict = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
        best_epoch = max(1, len(train_losses))
        best_train_loss = train_losses[-1] if train_losses else float("nan")

    return (
        {
            "backend": "torch",
            "input_dim": int(x_train.shape[1]),
            "hidden_dims": list(hidden_dims),
            "dropout": float(dropout),
            "output_activation": "sigmoid",
            "state_dict": best_state_dict,
        },
        train_losses,
        best_epoch,
        best_train_loss,
    )


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
        return np.clip(predictions.astype(float), 0.0, 1.0)
    if backend == "numpy_fallback":
        weights = np.asarray(model_payload["weights"], dtype=float)
        bias = float(model_payload["bias"])
        return _sigmoid(values @ weights + bias).astype(float)
    raise ValueError(f"Unsupported model backend: {backend!r}")


def fit_strength_model(
    train_df: pd.DataFrame,
    *,
    target_column: str = "strength_pct",
    hidden_dims: tuple[int, ...] = (64, 32),
    dropout: float = 0.1,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-5,
    batch_size: int = 32,
    max_epochs: int = 200,
    patience: int = 20,
    loss_function: str = "mse",
    target_weight_alpha: float = 1.0,
    target_weight_gamma: float = 2.0,
    random_seed: int = 42,
    backend: str = "auto",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if train_df.empty:
        raise ValueError("Training dataframe must not be empty.")
    if loss_function.lower() != "mse":
        raise ValueError("Only loss_function='mse' is supported.")

    df_model, feature_columns = _build_training_frame(train_df, target_column=target_column)
    x_all = df_model.loc[:, feature_columns].to_numpy(dtype=float)
    y_all = df_model[target_column].to_numpy(dtype=float)
    scaler = fit_standard_scaler(x_all, feature_columns=feature_columns)
    x_scaled = scaler.transform(x_all)

    resolved_backend = str(backend).lower()
    if resolved_backend == "auto":
        resolved_backend = "torch" if torch is not None else "numpy_fallback"

    if resolved_backend == "torch":
        model_payload, train_losses, best_epoch, best_train_loss = _fit_torch_model(
            x_scaled,
            y_all,
            hidden_dims=list(hidden_dims),
            dropout=dropout,
            learning_rate=learning_rate,
            weight_decay=weight_decay,
            batch_size=batch_size,
            max_epochs=max_epochs,
            patience=patience,
            target_weight_alpha=target_weight_alpha,
            target_weight_gamma=target_weight_gamma,
            random_seed=random_seed,
        )
    elif resolved_backend == "numpy_fallback":
        model_payload, train_losses, best_epoch, best_train_loss = _fit_numpy_fallback_model(
            x_scaled,
            y_all,
            alpha=target_weight_alpha,
            gamma=target_weight_gamma,
        )
    else:
        raise ValueError(f"Unsupported training backend: {resolved_backend!r}")

    predictions = predict_from_model_payload(model_payload, x_scaled)
    fit_metrics = _build_fit_metrics(y_all, predictions)

    model_params: dict[str, Any] = {
        "model_type": "mlp_regressor",
        "backend": resolved_backend,
        "input_dim": len(feature_columns),
        "hidden_dims": list(hidden_dims) if resolved_backend == "torch" else list(model_payload.get("hidden_dims", [])),
        "dropout": float(dropout) if resolved_backend == "torch" else float(model_payload.get("dropout", 0.0)),
        "output_activation": "sigmoid",
        "target_column": target_column,
        "feature_columns": list(feature_columns),
        "feature_count": len(feature_columns),
        "feature_order_locked": True,
        "scaler_type": "StandardScaler",
        "scaler_mean": list(scaler.mean_),
        "scaler_scale": list(scaler.scale_),
        "optimizer": "Adam",
        "learning_rate": float(learning_rate),
        "weight_decay": float(weight_decay),
        "batch_size": int(batch_size),
        "max_epochs": int(max_epochs),
        "patience": int(patience),
        "loss_function": loss_function.lower(),
        "target_weight_alpha": float(target_weight_alpha),
        "target_weight_gamma": float(target_weight_gamma),
        "random_seed": int(random_seed),
        "best_epoch": int(best_epoch),
        "best_train_loss": float(best_train_loss),
        "fit_metrics": fit_metrics,
        **model_payload,
    }
    train_logs = {
        "sample_count": int(len(df_model)),
        "feature_count": int(len(feature_columns)),
        "train_losses": [float(value) for value in train_losses],
        "best_epoch": int(best_epoch),
        "best_train_loss": float(best_train_loss),
        "fullfit_metrics": fit_metrics,
    }
    return model_params, train_logs


def predict_strength_pct(hist_df: pd.DataFrame, model_params: dict[str, Any]) -> np.ndarray:
    feature_columns = list(model_params.get("feature_columns", []))
    if not feature_columns:
        raise ValueError("model_params must contain non-empty feature_columns.")

    missing_columns = [column for column in feature_columns if column not in hist_df.columns]
    if missing_columns:
        raise ValueError(f"hist_df is missing required feature columns: {missing_columns}")

    ordered_df = hist_df.loc[:, feature_columns].copy()
    for column in feature_columns:
        ordered_df[column] = pd.to_numeric(ordered_df[column], errors="coerce")
    if ordered_df.isna().any().any():
        raise ValueError("hist_df contains missing or non-numeric values in required feature columns.")

    scaler = StandardScalerState(
        mean_=list(model_params["scaler_mean"]),
        scale_=list(model_params["scaler_scale"]),
        feature_columns=feature_columns,
    )
    scaled_values = scaler.transform(ordered_df.to_numpy(dtype=float))
    predictions = predict_from_model_payload(model_params, scaled_values)
    return np.clip(predictions.astype(float), 0.0, 1.0)


def train_buy_sub_ml_model(
    df: pd.DataFrame,
    feature_columns: list[str] | None = None,
    target_column: str = "strength_pct",
    config: dict | None = None,
) -> dict[str, Any]:
    if df.empty:
        raise ValueError("Training dataframe must not be empty.")

    merged_config = _merge_config(config)
    selected_feature_columns = feature_columns or select_hist_feature_columns(df)
    if feature_columns is not None and sorted(feature_columns) != list(selected_feature_columns):
        selected_feature_columns = sorted(feature_columns)

    train_input = df.loc[:, [*selected_feature_columns, target_column]].copy()
    model_params, train_logs = fit_strength_model(
        train_input,
        target_column=target_column,
        hidden_dims=tuple(merged_config["hidden_dims"]),
        dropout=float(merged_config["dropout"]),
        learning_rate=float(merged_config["learning_rate"]),
        weight_decay=float(merged_config["weight_decay"]),
        batch_size=int(merged_config["batch_size"]),
        max_epochs=int(merged_config["max_epochs"]),
        patience=int(merged_config["patience"]),
        loss_function=str(merged_config["loss_function"]),
        target_weight_alpha=float(merged_config["target_weight_alpha"]),
        target_weight_gamma=float(merged_config["target_weight_gamma"]),
        random_seed=int(merged_config["random_seed"]),
        backend=str(merged_config["backend"]),
    )

    prediction_columns = [
        *[column for column in ("ticker", "date", "datetime", "strength") if column in df.columns],
        *model_params["feature_columns"],
        target_column,
    ]
    predictions_df = df.loc[:, prediction_columns].dropna(
        subset=[*model_params["feature_columns"], target_column]
    ).copy()
    predictions_df["pred_strength_pct"] = predict_strength_pct(
        predictions_df.loc[:, model_params["feature_columns"]],
        model_params,
    )

    fit_metrics = train_logs["fullfit_metrics"]
    scaler = StandardScalerState(
        mean_=list(model_params["scaler_mean"]),
        scale_=list(model_params["scaler_scale"]),
        feature_columns=list(model_params["feature_columns"]),
    )
    return {
        "model": model_params,
        "model_params": model_params,
        "scaler": scaler,
        "metrics": {
            "overall": {
                "mae": float(fit_metrics["fullfit_mae"]),
                "rmse": float(fit_metrics["fullfit_rmse"]),
                "r2": float(fit_metrics["fullfit_r2"]),
                "pearson": float(fit_metrics["fullfit_pearson"]),
                "spearman": float(fit_metrics["fullfit_spearman"]),
                "rows": float(train_logs["sample_count"]),
            },
            "fit_metrics": fit_metrics,
        },
        "predictions": predictions_df,
        "train_config": {**merged_config, "resolved_backend": model_params["backend"]},
        "train_logs": train_logs,
        "split_counts": {
            "train_rows": int(train_logs["sample_count"]),
            "valid_rows": 0,
            "test_rows": 0,
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
    "fit_strength_model",
    "load_model_payload",
    "predict_from_model_payload",
    "predict_strength_pct",
    "save_model_payload",
    "train_buy_sub_ml_model",
]
