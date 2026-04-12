# Documentation Guide

`docs/` is the canonical home for project documentation.

## Structure

- `system_design.md`: top-level architecture, runtime modes, shared schema, development stages
- `api_reference.md`: code-grounded API and module integration reference for collaborators and other AI agents
- `modules/`: formal module specifications used for implementation
- `modules/minimal_closed_loop.md`: minimal end-to-end backtest loop plan, strategy definition, and usage
- `research/`: exploratory notes that may change quickly
- `changelog.md`: document and architecture change history

## Source Inventory

The following root-level files were reviewed and consolidated into the formal docs set:

- `auto_trading_system_design.md`
- `auto_trading_system_detailed.md`
- `auto_trading_system_implementation_spec.md`
- `Trend Engine Spec v1.md`
- `Budget Spec v1.md`
- `Daily Signal Spec v1.md`
- `Intraday Engine Spec v1.md`
- `Backtest Fill Spec v1.md`

## Status

- Root-level Markdown files remain in place as source drafts and history references.
- Formal updates should now prefer the `docs/` tree.
- Interface-level collaboration and cross-module handoff should prefer `docs/api_reference.md` plus the relevant `docs/modules/*.md`.
- The `backup/` directory is intentionally left untouched and should remain tracked in version control.
