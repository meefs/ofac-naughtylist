# Contributing

## How to add a new chain

1. Edit `config/chain_mapping.yaml`:
   - If the new chain has a unique OFAC ticker, add it to `direct_mappings`.
   - If the chain uses a distinct address format, add a regex pattern to `address_patterns`.
2. Add a test case to `tests/test_categorize.py` with a sample address.
3. Open a PR.

## How to report a misclassified address

Open an issue with:
- The address
- Expected chain
- Actual chain (where the tool placed it)
- The OFAC ticker it was listed under

## Code style

- Standard Python (PEP 8)
- Type hints on all function signatures

## Testing

- All PRs must pass `pytest`
- New features need test coverage
- Run tests locally: `pip install -r requirements-dev.txt && pytest tests/ -v`

## Commit messages

Conventional commits preferred but not enforced.
