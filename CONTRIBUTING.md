# Contributing

## Development setup

```bash
git clone https://github.com/madnihamza1841/duplicate-file-finder.git
cd duplicate-file-finder
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

The `dupfind` command is now available inside the virtual environment.

## Running the test suite

```bash
pytest tests/ -v
```

With coverage report:

```bash
pytest tests/ -v --cov=dupfinder --cov-report=term-missing
```

All tests use real temporary files via pytest's `tmp_path` fixture.
No external services or mocking are required.

## Trying it on the sample data

```bash
dupfind sample_data
dupfind sample_data --dry-run
dupfind sample_data --min-size 200
dupfind sample_data --output paths
```

## Code conventions

- Type hints on every public function and method signature
- Docstrings on every public function, method, and class
- No `TODO` or placeholder comments in committed code
- Python 3.9+ compatible syntax (`list[X]`, `X | None`, etc.)
- No dependencies outside the stdlib and the packages declared in `pyproject.toml`
