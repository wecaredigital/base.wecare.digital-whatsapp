#!/usr/bin/env python3
"""
Test script to verify handlers module imports and structure.
Run with: python tests/test_handlers_import.py
"""
import os
import sys

# Set required environment variables for testing
os.environ.setdefault("MESSAGES_TABLE_NAME", "test-table")
os.environ.setdefault("MESSAGES_PK_NAME", "pk")
os.environ.setdefault("MEDIA_BUCKET", "test-bucket")

def test_handlers_import():
    """Test that all handlers can be imported."""
    print("Testing handlers module import...")
    
    from handlers import (
        dispatch_extended_handler,
        list_extended_actions,
        get_extended_actions_by_category,
        EXTENDED_HANDLERS,
    )
    
    print(f"✓ Imported handlers module")
    print(f"✓ Total extended handlers: {len(EXTENDED_HANDLERS)}")
    
    # Test categories
    categories = get_extended_actions_by_category()
    print(f"✓ Categories: {len(categories)}")
    for cat, actions in categories.items():
        print(f"  - {cat}: {len(actions)} actions")
    
    # Test list_extended_actions
    actions = list_extended_actions()
    print(f"✓ Actions with descriptions: {len(actions)}")
    
    return True


def test_base_utilities():
    """Test base utilities import."""
    print("\nTesting base utilities...")
    
    from handlers.base import (
        iso_now,
        format_wa_number,
        validate_required_fields,
        success_response,
        error_response,
    )
    
    # Test iso_now
    now = iso_now()
    assert "T" in now, "iso_now should return ISO format"
    print(f"✓ iso_now(): {now}")
    
    # Test format_wa_number
    assert format_wa_number("1234567890") == "+1234567890"
    assert format_wa_number("+1234567890") == "+1234567890"
    print("✓ format_wa_number() works correctly")
    
    # Test validate_required_fields
    error = validate_required_fields({"a": 1}, ["a", "b"])
    assert error is not None
    assert error["statusCode"] == 400
    print("✓ validate_required_fields() works correctly")
    
    # Test response helpers
    resp = success_response("test", data={"key": "value"})
    assert resp["statusCode"] == 200
    assert resp["operation"] == "test"
    print("✓ success_response() works correctly")
    
    err = error_response("test error", 400)
    assert err["statusCode"] == 400
    assert err["error"] == "test error"
    print("✓ error_response() works correctly")
    
    return True


def test_app_import():
    """Test that app.py can be imported."""
    print("\nTesting app.py import...")
    
    from app import lambda_handler, api_response
    
    print("✓ Imported app.py successfully")
    print("✓ lambda_handler function available")
    print("✓ api_response function available")
    
    return True


def test_dispatch():
    """Test dispatch function."""
    print("\nTesting dispatch function...")
    
    from handlers import dispatch_extended_handler
    
    # Test with unknown action (should return None)
    result = dispatch_extended_handler("unknown_action", {}, None)
    assert result is None, "Unknown action should return None"
    print("✓ Unknown action returns None")
    
    # Test with known action (will fail due to missing params, but proves dispatch works)
    result = dispatch_extended_handler("get_business_profile", {}, None)
    assert result is not None, "Known action should return a response"
    assert "statusCode" in result, "Response should have statusCode"
    print(f"✓ Known action returns response: statusCode={result['statusCode']}")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Handler Module Tests")
    print("=" * 60)
    
    tests = [
        test_handlers_import,
        test_base_utilities,
        test_app_import,
        test_dispatch,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)
