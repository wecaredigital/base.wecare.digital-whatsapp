# Contributing

## Development Setup

```bash
# Clone
git clone https://github.com/wecaredigital/base.wecare.digital-whatsapp.git
cd base.wecare.digital-whatsapp

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v
```

## Adding a Handler

1. Create handler in appropriate module (`handlers/`)
2. Import and register in `handlers/extended.py`
3. Add to category in `get_extended_actions_by_category()`
4. Add tests in `tests/`

Example:
```python
# handlers/my_feature.py
def handle_my_action(event, context):
    """My action description."""
    return {"statusCode": 200, "result": "success"}

# handlers/extended.py
from handlers.my_feature import handle_my_action
EXTENDED_HANDLERS["my_action"] = handle_my_action
```

## Deployment

Push to `main` triggers auto-deploy via GitHub Actions.

Manual deploy:
```powershell
cd deploy
.\deploy-167-handlers.ps1
```

## Code Style

- Python 3.9+
- Type hints where practical
- Docstrings for handlers
- Error handling with proper status codes

## Pull Requests

1. Create feature branch
2. Add tests
3. Run `pytest tests/ -v`
4. Create PR to `main`
5. CI runs automatically
