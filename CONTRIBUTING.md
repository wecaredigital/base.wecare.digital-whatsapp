# Contributing

## Setup

```bash
git clone https://github.com/wecaredigital/base.wecare.digital-whatsapp.git
pip install -r requirements.txt
```

## Add Handler

1. Create in `handlers/my_feature.py`
2. Register in `handlers/extended.py`
3. Add tests in `tests/`

See [Development Guide](docs/DEVELOPMENT.md) for details.

## Deploy

Push to `main` → Auto-deploy via GitHub Actions.

## Test

```bash
python -m pytest tests/ -v
```
