#!/usr/bin/env python3
"""
Comprehensive test suite for the unified handler system.
Run with: python tests/test_unified_handlers.py
"""
import os
import sys

# Set required environment variables
os.environ.setdefault("MESSAGES_TABLE_NAME", "test-table")
os.environ.setdefault("MESSAGES_PK_NAME", "pk")
os.environ.setdefault("MEDIA_BUCKET", "test-bucket")


def test_unified_dispatcher():
    """Test the unified dispatcher."""
    print("=" * 60)
    print("Testing Unified Dispatcher")
    print("=" * 60)
    
    from handlers import (
        unified_dispatch,
        list_all_actions,
        list_actions_by_category,
        get_handler_count,
        handler_exists,
        generate_help,
        CATEGORIES,
    )
    from handlers.dispatcher import ensure_handlers_initialized
    
    # Ensure handlers are initialized before testing
    ensure_handlers_initialized()
    
    # Test handler count
    count = get_handler_count()
    print(f"✓ Total handlers registered: {count}")
    assert count > 0, "Should have handlers registered"
    
    # Test list_all_actions
    actions = list_all_actions()
    print(f"✓ Actions with descriptions: {len(actions)}")
    assert len(actions) == count, "All handlers should have descriptions"
    
    # Test list_actions_by_category
    by_category = list_actions_by_category()
    print(f"✓ Categories: {len(by_category)}")
    for cat, acts in sorted(by_category.items()):
        print(f"    {cat}: {len(acts)} handlers")
    
    # Test handler_exists
    assert handler_exists("get_business_profile"), "Should find get_business_profile"
    assert handler_exists("eum_get_supported_formats"), "Should find eum_get_supported_formats"
    assert not handler_exists("nonexistent_action"), "Should not find nonexistent action"
    print("✓ handler_exists() works correctly")
    
    # Test unified_dispatch with known action
    result = unified_dispatch("eum_get_supported_formats", {}, None)
    assert result is not None, "Should return result for known action"
    assert result.get("statusCode") == 200, "Should return success"
    print(f"✓ unified_dispatch() returns: statusCode={result['statusCode']}")
    
    # Test unified_dispatch with unknown action
    result = unified_dispatch("unknown_action_xyz", {}, None)
    assert result is None, "Should return None for unknown action"
    print("✓ unified_dispatch() returns None for unknown action")
    
    # Test generate_help
    help_doc = generate_help()
    assert "totalActions" in help_doc, "Help should have totalActions"
    assert "categories" in help_doc, "Help should have categories"
    print(f"✓ generate_help() returns {help_doc['totalActions']} actions in {len(help_doc['categories'])} categories")
    
    # Test CATEGORIES
    assert len(CATEGORIES) > 0, "Should have category definitions"
    print(f"✓ CATEGORIES defined: {len(CATEGORIES)}")
    
    return True


def test_base_utilities():
    """Test base utilities."""
    print("\n" + "=" * 60)
    print("Testing Base Utilities")
    print("=" * 60)
    
    from handlers import (
        iso_now,
        format_wa_number,
        validate_required_fields,
        validate_enum,
        success_response,
        error_response,
        not_found_response,
        SUPPORTED_MEDIA_TYPES,
        is_supported_media,
    )
    
    # Test iso_now
    now = iso_now()
    assert "T" in now and "+" in now, "Should return ISO format with timezone"
    print(f"✓ iso_now(): {now}")
    
    # Test format_wa_number
    assert format_wa_number("1234567890") == "+1234567890"
    assert format_wa_number("+1234567890") == "+1234567890"
    assert format_wa_number("") == ""
    print("✓ format_wa_number() works correctly")
    
    # Test validate_required_fields
    error = validate_required_fields({"a": 1}, ["a", "b"])
    assert error is not None and error["statusCode"] == 400
    error = validate_required_fields({"a": 1, "b": 2}, ["a", "b"])
    assert error is None
    print("✓ validate_required_fields() works correctly")
    
    # Test validate_enum
    error = validate_enum("invalid", ["a", "b"], "field")
    assert error is not None and error["statusCode"] == 400
    error = validate_enum("a", ["a", "b"], "field")
    assert error is None
    print("✓ validate_enum() works correctly")
    
    # Test response helpers
    resp = success_response("test", data={"key": "value"})
    assert resp["statusCode"] == 200 and resp["operation"] == "test"
    print("✓ success_response() works correctly")
    
    err = error_response("test error", 400)
    assert err["statusCode"] == 400 and err["error"] == "test error"
    print("✓ error_response() works correctly")
    
    nf = not_found_response("Item", "123")
    assert nf["statusCode"] == 404 and "123" in nf["error"]
    print("✓ not_found_response() works correctly")
    
    # Test media types
    assert len(SUPPORTED_MEDIA_TYPES) > 0
    result = is_supported_media("image/jpeg", 1000000)
    assert result["supported"] == True
    assert result["category"] == "image"
    print(f"✓ SUPPORTED_MEDIA_TYPES: {len(SUPPORTED_MEDIA_TYPES)} categories")
    
    return True


def test_app_integration():
    """Test app.py integration."""
    print("\n" + "=" * 60)
    print("Testing App Integration")
    print("=" * 60)
    
    from app import lambda_handler, api_response
    
    print("✓ Imported app.py successfully")
    print("✓ lambda_handler function available")
    print("✓ api_response function available")
    
    return True


def test_extended_handlers():
    """Test extended handlers."""
    print("\n" + "=" * 60)
    print("Testing Extended Handlers")
    print("=" * 60)
    
    from handlers import (
        get_extended_handlers,
        get_extended_actions_by_category,
        is_extended_action,
    )
    
    EXTENDED_HANDLERS = get_extended_handlers()
    
    print(f"✓ Extended handlers: {len(EXTENDED_HANDLERS)}")
    
    categories = get_extended_actions_by_category()
    print(f"✓ Extended categories: {len(categories)}")
    for cat, actions in categories.items():
        print(f"    {cat}: {len(actions)} handlers")
    
    # Verify all handlers in categories exist
    for cat, actions in categories.items():
        for action in actions:
            assert action in EXTENDED_HANDLERS, f"Action {action} should be in EXTENDED_HANDLERS"
            assert is_extended_action(action), f"is_extended_action should return True for {action}"
    print("✓ All categorized actions exist in EXTENDED_HANDLERS")
    
    return True


def test_handler_dispatch():
    """Test dispatching various handlers."""
    print("\n" + "=" * 60)
    print("Testing Handler Dispatch")
    print("=" * 60)
    
    from handlers import unified_dispatch
    
    test_cases = [
        # (action, event, expected_status)
        ("eum_get_supported_formats", {}, 200),
        ("eum_validate_media", {"mimeType": "image/jpeg"}, 200),
        ("get_business_profile", {}, 400),  # Missing required field
        ("get_analytics", {}, 400),  # Missing required field
    ]
    
    for action, event, expected_status in test_cases:
        result = unified_dispatch(action, event, None)
        if result:
            actual_status = result.get("statusCode", 0)
            status = "✓" if actual_status == expected_status else "✗"
            print(f"{status} {action}: statusCode={actual_status} (expected {expected_status})")
        else:
            print(f"✗ {action}: returned None")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("UNIFIED HANDLER SYSTEM - TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        test_unified_dispatcher,
        test_base_utilities,
        test_app_integration,
        test_extended_handlers,
        test_handler_dispatch,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
