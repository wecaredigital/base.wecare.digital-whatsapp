# Contributing Guide

## Development Setup

1. Clone the repository
2. Install Python 3.12+
3. Install dependencies: `pip install -r requirements.txt`
4. Configure AWS credentials

## Adding a New Handler

### Option 1: Using Decorator (Recommended)

```python
# In handlers/your_feature.py
from handlers.dispatcher import register

@register("your_action", category="your_category", requires=["param1", "param2"])
def handle_your_action(event, context):
    """Short description of what this handler does."""
    param1 = event.get("param1")
    param2 = event.get("param2")
    
    # Your logic here
    
    return {
        "statusCode": 200,
        "operation": "your_action",
        "result": "success"
    }
```

### Option 2: Add to Extended Handlers

1. Create handler in `handlers/your_feature.py`
2. Import in `handlers/extended.py`
3. Add to `EXTENDED_HANDLERS` dict:

```python
from handlers.your_feature import handle_your_action

EXTENDED_HANDLERS = {
    # ... existing handlers
    "your_action": handle_your_action,
}
```

4. Add to `get_extended_actions_by_category()` for documentation

## Handler Guidelines

1. **Always return a dict** with `statusCode`
2. **Validate required params** at the start
3. **Use descriptive docstrings** (first line becomes description)
4. **Log important operations** using `logger.info()`
5. **Handle errors gracefully** - return 400/500 with error message

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_all_handlers.py -v

# Test handler count
python -c "from handlers.extended import EXTENDED_HANDLERS; print(len(EXTENDED_HANDLERS))"
```

## Code Style

- Use Black for formatting: `black app.py handlers/`
- Use isort for imports: `isort app.py handlers/`
- Max line length: 120 characters
- Use type hints where practical

## Pull Request Process

1. Create feature branch from `main`
2. Make changes
3. Run tests locally
4. Push and create PR
5. Wait for CI checks to pass
6. Get code review
7. Merge to `main` (auto-deploys)

## Deployment

Deployments are automatic via GitHub Actions:
- Push to `main` → Deploy to Lambda
- PR → Run tests only

Manual deployment:
```powershell
powershell -File deploy/deploy-167-handlers.ps1
```

## Questions?

Contact: base@wecare.digital
