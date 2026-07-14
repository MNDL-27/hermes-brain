# hermes-brain

Unified AI agent brain for the agentinc AI ecosystem.

## Features

- Skill and plugin management for AI agents
- Schema validation and data extraction
- Persistent store with bootstrap support

## Installation

```bash
pip install -e .
```

## Usage

```python
from hermes_brain import bootstrap, store

s = store.Store()
bootstrap.init(s)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
