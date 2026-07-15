# Contributing

Thanks for your interest in contributing to hermes-brain! This document outlines how to contribute effectively.

## Ways to Contribute

- **Bug reports** — Found something broken? Open an issue with steps to reproduce
- **Feature requests** — Have an idea? Open an issue with the `enhancement` label
- **Code contributions** — Fix bugs, add features, improve performance
- **Documentation** — Improve README, add examples, write guides
- **Testing** — Add test coverage, report edge cases

## Backend Scope

The Notion backend is the only backend in this repository today. Future backends (Obsidian, SQLite, Logseq, local Markdown vault) are part of the same project when they land — there is no separate paid package or paid companion repo to contribute to. Backend feature PRs are welcome as soon as the maintainer opens the scope for one.

If you want to build your own backend, see [`BACKEND_SWAP_GUIDE.md`](BACKEND_SWAP_GUIDE.md).

## Development Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/hermes-brain.git
cd hermes-brain

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_schema.py -v
```

## Code Quality

```bash
# Lint with ruff
ruff check .

# Auto-fix linting issues
ruff check . --fix

# Format with ruff
ruff format .

# Type check with mypy
mypy .
```

## Making Changes

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-change-name
```

Branch naming convention:
- `feature/short-description` — new features
- `fix/short-description` — bug fixes
- `docs/short-description` — documentation only
- `refactor/short-description` — code restructuring
- `test/short-description` — test additions

### 2. Write Code

Follow these guidelines:
- **Type hints** on all public functions
- **Docstrings** for all public classes/functions (Google style)
- **Stdlib first** — avoid new dependencies unless necessary
- **Small, focused commits** — one logical change per commit
- **Tests for new functionality** — aim for >80% coverage on new code

### 3. Run Quality Checks

Before pushing, run locally:

```bash
ruff check .
ruff format .
mypy .
pytest --cov=. --cov-report=term-missing
```

### 4. Commit Messages

Use conventional commits:

```
type(scope): brief description

Longer explanation if needed.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

Examples:
```
feat(extract): add new trigger pattern for meeting notes
fix(store): handle 429 rate limit with exponential backoff
docs(readme): add configuration section with examples
```

### 5. Push and Open PR

```bash
git push origin feature/your-change-name
```

Open a Pull Request against `main`. The PR template will guide you.

## Project Structure

```
hermes-brain/
├── __init__.py          # Plugin entry point, tool schemas, provider
├── schema.py            # Data model, constants, normalization helpers
├── extract.py           # Heuristic classifier (regex patterns)
├── store.py             # Notion REST API client
├── bootstrap.py         # Workspace setup, database creation
├── plugin.yaml          # Plugin manifest
├── tests/               # Test files (add here)
├── .github/
│   ├── workflows/       # CI/CD
│   ├── assets/          # Images for README
│   └── badges/          # Coverage badge
└── docs/                # Additional documentation (future)
```

## Adding New Features

### New Heuristic Trigger (in `extract.py`)

1. Add a new `_TRIGGERS_*` regex pattern (see lines 17-51)
2. Add a new `if` block in `classify_turn()` (see lines 79-143)
3. Add corresponding domain to `DOMAIN_DATABASE` in `schema.py` if needed
4. Add tests for the new pattern

### New Tool Schema (in `__init__.py`)

1. Define a new schema dict following the pattern of `SEARCH_SCHEMA` (line 29)
2. Add to `ALL_TOOL_SCHEMAS` list (line 239)
3. Add handler method `_tool_yourname()` (see `_tool_search` at line 576)
4. Add dispatch in `handle_tool_call()` (line 477)
5. Add tests

### New Database Property

1. Add property definition in `bootstrap.py` `_PROPS` dict (lines 20-101)
2. Update corresponding handler in `__init__.py` to populate the property
3. Run bootstrap to verify creation

## Testing Guidelines

- Test files go in `tests/` mirroring source structure
- Use `pytest` fixtures for common setup
- Mock Notion API calls — don't hit real API in tests
- Test both happy path and edge cases
- Property-based testing for normalization functions

## Release Process

Releases are automated via GitHub Actions on tag push:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The CI will:
1. Run all tests on Python 3.10-3.13
2. Build package
3. Publish to PyPI (if `PYPI_API_TOKEN` secret is set)
4. Create GitHub Release with changelog

## Code of Conduct

By participating, you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md). In short:

- Be respectful and inclusive
- Welcome newcomers
- Focus on what's best for the project
- No harassment, discrimination, or toxic behavior

## Getting Help

- **GitHub Discussions** — for questions, ideas, general discussion
- **GitHub Issues** — for bugs and feature requests
- **Discord** — [Join our server](https://discord.gg/your-invite) for real-time chat

## Recognition

Contributors are recognized in:
- GitHub Contributors graph
- Release notes
- README acknowledgments (for significant contributions)

Thank you for contributing to hermes-brain!