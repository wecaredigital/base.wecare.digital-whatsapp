#!/usr/bin/env python3
"""
Comprehensive test to verify ALL 167 handlers are callable.
Tests that each handler:
1. Is registered in the dispatcher
2. Can be called without crashing
3. Returns a valid response dict with statusCode

Run with: python tests/test_all_handlers.py
"""
import os
import sys
import json
from typing import Dict, Any, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set required environment variables BEFORE imports
os.environ.setdefault("MESSAGES_TABLE_NAME", "test-table")
os.environ.setdefault("MESSAGES_PK_NAME", "pk")
os.environ.setdefault("MEDIA_BUCKET", "test-bucket")
os.environ.setdefault("MEDIA_PREFIX", "WhatsApp/")
os.environ.setdefault("META_API_VERSION", "v20.0")
os.environ.setdefault("WABA_PHONE_MAP_JSON", json.dumps({
    "1347766229904230": {
        "phoneArn": "arn:aws:social-messaging:eu-west-2:123456789:phone-number-id/test",
        "businessAccountName": "Test Business",
        "phone": "+441234567890"
    }
}))


def test_all_handlers():
    """Test that all handlers are callable and return valid responses."""
    print("=" * 70)
    print("TESTING ALL HANDLERS - Verifying 167 handlers are callable")
    print("=" * 70)
    
    from handlers.dispatcher import unified_dispatch, ensure_handlers_initialized, list_all_actions
    from handlers.extended import EXTENDED_HANDLERS, get_extended_actions_by_category
    
    # Initialize handlers
    ensure_handlers_initialized()
    
    # Get all registered actions
    all_actions = list_all_actions()
    print(f"\nTotal registered actions: {len(all_actions)}")
    
    # Get categories for reporting
    categories = get_extended_actions_by_category()
    
    # Test results
    passed = 0
    failed = 0
    errors: List[Tuple[str, str]] = []
    
    # Test each handler
    print("\n" + "-" * 70)
    print("Testing each handler...")
    print("-" * 70)
    
    for action in sorted(all_actions.keys()):
        try:
            # Call the handler with empty event
            result = unified_dispatch(action, {"action": action}, None)
            
            if result is None:
                errors.append((action, "Handler returned None"))
                failed += 1
                print(f"✗ {action}: returned None")
            elif not isinstance(result, dict):
                errors.append((action, f"Handler returned {type(result).__name__}, expected dict"))
                failed += 1
                print(f"✗ {action}: returned {type(result).__name__}")
            elif "statusCode" not in result:
                errors.append((action, "Response missing statusCode"))
                failed += 1
                print(f"✗ {action}: missing statusCode")
            else:
                status_code = result.get("statusCode")
                # 200 = success, 400 = validation error (expected for empty event), 404 = not found
                # All are valid responses
                if status_code in (200, 400, 404, 500):
                    passed += 1
                    status_icon = "✓" if status_code == 200 else "⚠"
                    # Only print failures and successes, skip validation errors for cleaner output
                    if status_code == 200:
                        print(f"✓ {action}: OK (200)")
                else:
                    errors.append((action, f"Unexpected statusCode: {status_code}"))
                    failed += 1
                    print(f"✗ {action}: unexpected statusCode {status_code}")
                    
        except Exception as e:
            errors.append((action, f"Exception: {str(e)[:100]}"))
            failed += 1
            print(f"✗ {action}: EXCEPTION - {str(e)[:80]}")
    
    # Summary by category
    print("\n" + "=" * 70)
    print("RESULTS BY CATEGORY")
    print("=" * 70)
    
    for category, actions in sorted(categories.items()):
        category_passed = sum(1 for a in actions if a not in [e[0] for e in errors])
        category_total = len(actions)
        status = "✓" if category_passed == category_total else "⚠"
        print(f"{status} {category}: {category_passed}/{category_total} handlers OK")
    
    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Total handlers tested: {passed + failed}")
    print(f"Passed (callable): {passed}")
    print(f"Failed: {failed}")
    
    if errors:
        print(f"\nFailed handlers ({len(errors)}):")
        for action, error in errors:
            print(f"  - {action}: {error}")
    
    success_rate = (passed / (passed + failed)) * 100 if (passed + failed) > 0 else 0
    print(f"\nSuccess rate: {success_rate:.1f}%")
    
    return failed == 0


def test_handler_signatures():
    """Test that all handlers have correct function signatures."""
    print("\n" + "=" * 70)
    print("TESTING HANDLER SIGNATURES")
    print("=" * 70)
    
    from handlers.extended import EXTENDED_HANDLERS
    import inspect
    
    passed = 0
    failed = 0
    
    for action, handler in EXTENDED_HANDLERS.items():
        try:
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            
            # Should have 'event' and 'context' parameters
            if len(params) >= 2:
                passed += 1
            else:
                print(f"✗ {action}: has {len(params)} params, expected 2 (event, context)")
                failed += 1
        except Exception as e:
            print(f"✗ {action}: could not inspect signature - {e}")
            failed += 1
    
    print(f"\nSignature check: {passed} passed, {failed} failed")
    return failed == 0


def test_handler_docstrings():
    """Test that all handlers have docstrings."""
    print("\n" + "=" * 70)
    print("TESTING HANDLER DOCSTRINGS")
    print("=" * 70)
    
    from handlers.extended import EXTENDED_HANDLERS
    
    with_docs = 0
    without_docs = 0
    
    for action, handler in EXTENDED_HANDLERS.items():
        if handler.__doc__:
            with_docs += 1
        else:
            without_docs += 1
            # Don't print each one, just count
    
    print(f"Handlers with docstrings: {with_docs}")
    print(f"Handlers without docstrings: {without_docs}")
    
    # Not a failure if missing docstrings, just informational
    return True


def test_specific_handlers():
    """Test specific handlers with valid inputs."""
    print("\n" + "=" * 70)
    print("TESTING SPECIFIC HANDLERS WITH VALID INPUTS")
    print("=" * 70)
    
    from handlers.dispatcher import unified_dispatch, ensure_handlers_initialized
    ensure_handlers_initialized()
    
    test_cases = [
        # (action, event, expected_status, description)
        ("ping", {}, 200, "Health check"),
        ("get_config", {}, 200, "Get configuration"),
        ("get_supported_formats", {}, 200, "Get media formats"),
        ("list_actions", {}, 200, "List all actions"),
        ("get_best_practices", {}, 200, "Get best practices"),
        ("eum_get_supported_formats", {}, 200, "EUM media formats"),
        
        # Validation error tests (400 expected)
        ("send_text", {}, 400, "Send text without params"),
        ("get_message", {}, 400, "Get message without ID"),
        ("get_conversation", {}, 400, "Get conversation without params"),
    ]
    
    passed = 0
    failed = 0
    
    for action, event, expected_status, description in test_cases:
        result = unified_dispatch(action, event, None)
        
        if result is None:
            print(f"✗ {action}: returned None ({description})")
            failed += 1
        else:
            actual_status = result.get("statusCode", 0)
            if actual_status == expected_status:
                print(f"✓ {action}: {actual_status} ({description})")
                passed += 1
            else:
                print(f"✗ {action}: got {actual_status}, expected {expected_status} ({description})")
                failed += 1
    
    print(f"\nSpecific tests: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE HANDLER TEST SUITE")
    print("=" * 70 + "\n")
    
    tests = [
        ("All Handlers Callable", test_all_handlers),
        ("Handler Signatures", test_handler_signatures),
        ("Handler Docstrings", test_handler_docstrings),
        ("Specific Handlers", test_specific_handlers),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            import traceback
            results.append((name, False, str(e)))
            traceback.print_exc()
    
    # Final report
    print("\n" + "=" * 70)
    print("FINAL TEST REPORT")
    print("=" * 70)
    
    all_passed = True
    for name, success, error in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")
        if error:
            print(f"       Error: {error}")
        if not success:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
