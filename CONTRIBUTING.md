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

If you want to build your own backend or extend the classifier, see
[`docs/backend-guide.md`](docs/backend-guide.md).

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
pytest tests/test_extract.py -v
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
├── notion_brain/
│   ├── __init__.py          # Plugin exports & discovery marker
│   ├── provider.py          # NotionBrainProvider lifecycle & tool dispatch
│   ├── store.py             # Notion REST API client & block pagination
│   ├── extract.py           # Heuristic & LLM classifier
│   ├── schema.py            # Data model, constants, secret redaction
│   ├── schemas.py           # OpenAI-compatible tool schemas for Hermes
│   ├── bootstrap.py         # Workspace setup, schema repair, setup wizard
│   ├── helpers.py           # Block and text helpers
│   ├── config_schema.py     # Desktop config declaration
│   └── __main__.py          # CLI commands (setup, health, reset, url)
├── skills/
│   └── notion-brain/        # Hermes Agent companion skill
├── tests/                   # Pytest test suite
├── examples/                # Quickstart and migration scripts
├── docs/                    # Architecture and troubleshooting guides
├── plugin.yaml              # Plugin manifest
└── pyproject.toml           # Package configuration & entry points
```

## Adding New Features

### New Heuristic Trigger (in `notion_brain/extract.py`)

1. Add a new `_TRIGGERS_*` regex pattern
2. Add a new classification branch in `classify_turn()`
3. Add corresponding domain to `DOMAIN_DATABASE` in `notion_brain/schema.py` if needed
4. Add tests in `tests/test_extract.py`

### New Tool Schema (in `notion_brain/schemas.py`)

1. Define a new schema dictionary in `notion_brain/schemas.py`
2. Add it to the `ALL_TOOL_SCHEMAS` list
3. Add the handler method `_tool_yourname()` in `notion_brain/provider.py`
4. Add dispatch in `handle_tool_call()` in `notion_brain/provider.py`
5. Add unit tests in `tests/test_provider.py`

### New Database Property

1. Add property definition in `notion_brain/bootstrap.py` `_PROPS` dict
2. Update corresponding property builder in `notion_brain/provider.py`
3. Run `hermes-brain reset` or tests to verify schema creation

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
- **GitHub Discussions** — for questions, ideas, and general discussion
- **GitHub Issues** — for bugs and feature requests
- **Discord** — [Nous Research Discord](https://discord.gg/nousresearch) `#plugins-skills-and-skins`

## Recognition

Contributors are recognized in:
- GitHub Contributors graph
- Release notes
- README acknowledgments (for significant contributions)

Thank you for contributing to hermes-brain!