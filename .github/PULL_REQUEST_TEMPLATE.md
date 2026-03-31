## Summary

- describe the main change
- note whether the change is code, docs, or repository management

## Affected Areas

- [ ] `.github/`
- [ ] `app/`
- [ ] `backup/`
- [ ] `config/`
- [ ] `docs/`
- [ ] `scripts/`
- [ ] `tests/`

## Checks

- [ ] I kept `backup/` intact and included it in version control if relevant
- [ ] I updated `docs/` when behavior or design changed
- [ ] I kept GitHub Actions manual-only
- [ ] I ran `python scripts/init_db.py --config config/backtest.yaml`
- [ ] I ran `python -m pytest -q`

## Notes

- mention any intentional placeholders or deferred work
