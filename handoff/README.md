# Handoff Area

This directory is the shared baton between daytime Claude sessions and nighttime Codex sessions.

## Files

- `CURRENT.md`: single source of truth for what is in progress right now
- `TODO.md`: prioritized next work items
- `DECISIONS.md`: architectural or workflow decisions worth preserving
- `SESSION_LOG.md`: short chronological notes after each working session

## Minimal Handoff Rule

Before stopping, update only two places:

1. `CURRENT.md`
2. `SESSION_LOG.md`

That is enough for the next agent to continue without rereading the whole repo.

## Suggested Workflow

1. Read `CURRENT.md`
2. Skim `TODO.md` if the current task is blocked or done
3. Check `DECISIONS.md` before changing architecture or workflow assumptions
4. Append a short note to `SESSION_LOG.md` when finishing

## Writing Style

Keep notes short, concrete, and operational:

- what changed
- what still fails
- what command was last run
- what should happen next

Avoid long narratives. Optimize for fast continuation on a phone or late-night coding session.
