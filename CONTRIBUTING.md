# Contributing

## Setup

```bash
git clone https://github.com/madnihamza1841/duplicate-file-finder.git
cd duplicate-file-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest tests/ -v --cov=dupfinder --cov-report=term-missing
```

All tests use real temporary files via pytest's `tmp_path` fixture — no mocking. The suite should pass cleanly and show ≥80% coverage.

## Code style

- Type hints on all public functions
- No placeholder TODOs in committed code
- Python 3.9+ compatible syntax
