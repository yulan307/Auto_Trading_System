# Decisions

## 2026-04-14 - Use a repo-local handoff area

Decision:
Store collaboration state in a root-level `handoff/` directory.

Why:
Both Claude and Codex can find it quickly, and it keeps session continuity inside the repo instead of a separate chat history.

Tradeoff:
It adds a few markdown files to the repository, but the continuity benefit is worth the extra surface area.

## 2026-04-14 - Keep the handoff format lightweight

Decision:
Use four small markdown files instead of a heavier project management system.

Why:
This project is still moving quickly, and handoff notes need to be easy to update from mobile or at the end of a coding session.

Tradeoff:
The notes depend on discipline rather than automation, so each session should at least update `CURRENT.md` and `SESSION_LOG.md`.
