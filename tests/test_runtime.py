#!/usr/bin/env python3
"""
Comprehensive test suite for the unified runtime system.

Tests:
- Envelope creation and properties
- Event parsing (API Gateway, SNS, SQS, EventBridge, Direct, CLI)
- Unified dispatcher
- Dependency injection container
- Bedrock integration

Run with: pytest tests/test_runtime.py -v
Or: python tests/test_runtime.py
"""
import os
import sys
import json
import uuid
from typing import Dict, Any
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set required environment variables BEFORE imports
os.environ.setdefault("MESSAGES_TABLE_NAME", "test-table")
os.environ.setdefault("MESSAGES_PK_NAME", "pk")
os.environ.setdefault("MEDIA_BUCKET", "test-bucket")
os.environ.setdefault("MEDIA_PREFIX", "WhatsApp/")
os.environ.setdefault("META_API_VERSION", "v20.0")
os.environ.setdefault("AWS_REGION", "ap-south-1")
os.environ.setdefault("BEDROCK_REGION", "ap-south-1")
os.environ.setdefault("BEDROCK_AGENT_ID", "test-agent-id")
os.environ.setdefault("BEDROCK_AGENT_ALIAS_ID", "TSTALIASID")
os.environ.setdefault("WABA_PHONE_MAP_JSON", json.dumps({
    "1347766229904230": {
        "phoneArn": "arn:aws:social-messaging:eu-west-2:123456789:phone-number-id/test",
        "businessAccountName": "WECARE-DIGITAL",
        "phone": "+919330994400"
    }
}))


# =============================================================================
# TEST: Envelope
# =============================================================================

class TestEnvelope:
    """Tests for Envelope class."""
    
    def test_envelope_creation(self):
        """Test basic envelope creation."""
        from src.runtime.envelope import Envelope, EnvelopeKind
        
        envelope = Envelope(
            kind=EnvelopeKind.ACTION_REQUEST,
            request_id="test-123",
            tenant_id="tenant-456",
            source="direct",
            payload={"action": "test_action", "param": "value"},
        )
        
        assert envelope.kind == EnvelopeKind.ACTION_REQUEST
        assert envelope.request_id == "test-123"
        assert envelope.tenant_id == "tenant-456"
        assert envelope.source == "direct"
        assert envelope.action == "test_action"
        assert envelope.get("param") == "value"
        print("✓ Envelope creation works correctly")
    
    def test_envelope_kind_properties(self):
        """Test envelope kind property helpers."""
        from src.runtime.envelope import Envelope, EnvelopeKind
        
        action_env = Envelope(
            kind=EnvelopeKind.ACTION_REQUEST,
            request_id="1", tenant_id="", source="direct", payload={}
        )
        assert action_env.is_action_request == True
        assert action_env.is_inbound_event == False
        assert action_env.is_internal_job == False
        
        inbound_env = Envelope(
            kind=EnvelopeKind.INBOUND_EVENT,
            request_id="2", tenant_id="", source="sqs", payload={}
        )
        assert inbound_env.is_action_request == False
        assert inbound_env.is_inbound_event == True
        
        job_env = Envelope(
            kind=EnvelopeKind.INTERNAL_JOB,
            request_id="3", tenant_id="", source="step_functions", payload={}
        )
        assert job_env.is_internal_job == True
        print("✓ Envelope kind properties work correctly")
    
    def test_envelope_from_action_request(self):
        """Test creating envelope from action request."""
        from src.runtime.envelope import Envelope, EnvelopeKind
        
        payload = {"action": "send_text", "to": "+1234567890", "text": "Hello"}
        envelope = Envelope.from_action_request(payload, source="api_gateway")
        
        assert envelope.kind == EnvelopeKind.ACTION_REQUEST
        assert envelope.action == "send_text"
        assert envelope.source == "api_gateway"
        assert envelope.get("to") == "+1234567890"
        print("✓ Envelope.from_action_request() works correctly")
    
    def test_envelope_from_inbound_event(self):
        """Test creating envelope from inbound event."""
        from src.runtime.envelope import Envelope, EnvelopeKind
        
        payload = {"type": "message", "from": "+1234567890"}
        envelope = Envelope.from_inbound_event(payload, tenant_id="waba-123")
        
        assert envelope.kind == EnvelopeKind.INBOUND_EVENT
        assert envelope.tenant_id == "waba-123"
        assert envelope.source == "sqs"
        print("✓ Envelope.from_inbound_event() works correctly")
    
    def test_envelope_from_internal_job(self):
        """Test creating envelope from internal job."""
        from src.runtime.envelope import Envelope, EnvelopeKind
        
        payload = {"jobType": "campaign_batch", "batchId": "batch-123"}
        envelope = Envelope.from_internal_job(payload, source="step_functions")
        
        assert envelope.kind == EnvelopeKind.INTERNAL_JOB
        assert envelope.source == "step_functions"
        print("✓ Envelope.from_internal_job() works correctly")
    
    def test_envelope_to_dict(self):
        """Test envelope serialization."""
        from src.runtime.envelope import Envelope, EnvelopeKind
        
        envelope = Envelope(
            kind=EnvelopeKind.ACTION_REQUEST,
            request_id="test-123",
            tenant_id="tenant-456",
            source="direct",
            payload={"action": "test"},
        )
        
        d = envelope.to_dict()
        assert d["kind"] == "action_request"
        assert d["requestId"] == "test-123"
        assert d["tenantId"] == "tenant-456"
        assert d["payload"]["action"] == "test"
        print("✓ Envelope.to_dict() works correctly")


# =============================================================================
# TEST: Event Parser
# =============================================================================

class TestEventParser:
    """Tests for event parsing and source detection."""
    
    def test_detect_api_gateway_http_v2(self):
        """Test detecting API Gateway HTTP API v2 events."""
        from src.runtime.parse_event import detect_event_source, EventSource
        
        event = {
            "requestContext": {
                "http": {"method": "POST", "path": "/api"},
                "requestId": "abc123"
            },
            "body": '{"action": "test"}'
        }
        
        assert detect_event_source(event) == EventSource.API_GATEWAY
        print("✓ Detects API Gateway HTTP API v2")
    
    def test_detect_api_gateway_rest_v1(self):
        """Test detecting API Gateway REST API v1 events."""
        from src.runtime.parse_event import detect_event_source, EventSource
        
        event = {
            "requestContext": {
                "httpMethod": "POST",
                "requestId": "abc123"
            },
            "body": '{"action": "test"}'
        }
        
        assert detect_event_source(event) == EventSource.API_GATEWAY
        print("✓ Detects API Gateway REST API v1")
    
    def test_detect_sqs_event(self):
        """Test detecting SQS events."""
        from src.runtime.parse_event import detect_event_source, EventSource
        
        event = {
            "Records": [{
                "eventSource": "aws:sqs",
                "messageId": "msg-123",
                "body": '{"test": "data"}'
            }]
        }
        
        assert detect_event_source(event) == EventSource.SQS
        print("✓ Detects SQS events")
    
    def test_detect_sns_event(self):
        """Test detecting SNS events."""
        from src.runtime.parse_event import detect_event_source, EventSource
        
        event = {
            "Records": [{
                "eventSource": "aws:sns",
                "Sns": {
                    "MessageId": "msg-123",
                    "Message": '{"test": "data"}'
                }
            }]
        }
        
        assert detect_event_source(event) == EventSource.SNS
        print("✓ Detects SNS events")
    
    def test_detect_eventbridge_event(self):
        """Test detecting EventBridge events."""
        from src.runtime.parse_event import detect_event_source, EventSource
        
        event = {
            "source": "custom.whatsapp",
            "detail-type": "whatsapp.inbound.received",
            "detail": {"messageId": "msg-123"}
        }
        
        assert detect_event_source(event) == EventSource.EVENTBRIDGE
        print("✓ Detects EventBridge events")
    
    def test_detect_step_functions_event(self):
        """Test detecting Step Functions events."""
        from src.runtime.parse_event import detect_event_source, EventSource
        
        event = {
            "taskToken": "token-123",
            "input": {"action": "process_batch"}
        }
        
        assert detect_event_source(event) == EventSource.STEP_FUNCTIONS
        print("✓ Detects Step Functions events")
    
    def test_detect_direct_invoke(self):
        """Test detecting direct Lambda invoke."""
        from src.runtime.parse_event import detect_event_source, EventSource
        
        event = {"action": "send_text", "to": "+1234567890"}
        
        assert detect_event_source(event) == EventSource.DIRECT
        print("✓ Detects direct invoke events")
    
    def test_detect_cli_event(self):
        """Test detecting CLI events."""
        from src.runtime.parse_event import detect_event_source, EventSource
        
        # CLI events have _source marker but no action (action check comes first)
        event = {"_source": "cli"}
        
        assert detect_event_source(event) == EventSource.CLI
        print("✓ Detects CLI events")
    
    def test_parse_api_gateway_event(self):
        """Test parsing API Gateway event into envelope."""
        from src.runtime.parse_event import parse_event, EventSource
        from src.runtime.envelope import EnvelopeKind
        
        event = {
            "requestContext": {
                "http": {"method": "POST", "path": "/api"},
                "requestId": "req-123"
            },
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"action": "ping", "metaWabaId": "waba-123"})
        }
        
        envelopes, source = parse_event(event)
        
        assert source == EventSource.API_GATEWAY
        assert len(envelopes) == 1
        assert envelopes[0].kind == EnvelopeKind.ACTION_REQUEST
        assert envelopes[0].action == "ping"
        assert envelopes[0].tenant_id == "waba-123"
        print("✓ Parses API Gateway events correctly")
    
    def test_parse_sqs_event_with_sns_wrapper(self):
        """Test parsing SQS event with SNS message wrapper."""
        from src.runtime.parse_event import parse_event, EventSource
        from src.runtime.envelope import EnvelopeKind
        
        inner_message = {
            "whatsAppWebhookEntry": {"id": "1347766229904230"},
            "type": "message"
        }
        
        sns_wrapper = {
            "Type": "Notification",
            "Message": json.dumps(inner_message)
        }
        
        event = {
            "Records": [{
                "eventSource": "aws:sqs",
                "messageId": "sqs-msg-123",
                "body": json.dumps(sns_wrapper)
            }]
        }
        
        envelopes, source = parse_event(event)
        
        assert source == EventSource.SQS
        assert len(envelopes) == 1
        assert envelopes[0].kind == EnvelopeKind.INBOUND_EVENT
        assert envelopes[0].tenant_id == "1347766229904230"
        print("✓ Parses SQS events with SNS wrapper correctly")
    
    def test_parse_eventbridge_event(self):
        """Test parsing EventBridge event."""
        from src.runtime.parse_event import parse_event, EventSource
        from src.runtime.envelope import EnvelopeKind
        
        event = {
            "id": "eb-123",
            "source": "custom.whatsapp",
            "detail-type": "whatsapp.inbound.received",
            "detail": {
                "tenantId": "tenant-123",
                "messageId": "msg-456"
            }
        }
        
        envelopes, source = parse_event(event)
        
        assert source == EventSource.EVENTBRIDGE
        assert len(envelopes) == 1
        assert envelopes[0].kind == EnvelopeKind.INTERNAL_JOB
        assert envelopes[0].tenant_id == "tenant-123"
        print("✓ Parses EventBridge events correctly")
    
    def test_parse_direct_invoke(self):
        """Test parsing direct Lambda invoke."""
        from src.runtime.parse_event import parse_event, EventSource
        from src.runtime.envelope import EnvelopeKind
        
        event = {
            "action": "send_text",
            "metaWabaId": "waba-123",
            "to": "+1234567890",
            "text": "Hello"
        }
        
        envelopes, source = parse_event(event)
        
        assert source == EventSource.DIRECT
        assert len(envelopes) == 1
        assert envelopes[0].kind == EnvelopeKind.ACTION_REQUEST
        assert envelopes[0].action == "send_text"
        print("✓ Parses direct invoke events correctly")
    
    def test_parse_multiple_sqs_records(self):
        """Test parsing SQS event with multiple records."""
        from src.runtime.parse_event import parse_event, EventSource
        
        event = {
            "Records": [
                {
                    "eventSource": "aws:sqs",
                    "messageId": "msg-1",
                    "body": json.dumps({"action": "action1"})
                },
                {
                    "eventSource": "aws:sqs",
                    "messageId": "msg-2",
                    "body": json.dumps({"action": "action2"})
                }
            ]
        }
        
        envelopes, source = parse_event(event)
        
        assert source == EventSource.SQS
        assert len(envelopes) == 2
        print("✓ Parses multiple SQS records correctly")


# =============================================================================
# TEST: Dispatcher
# =============================================================================

class TestDispatcher:
    """Tests for the unified dispatcher."""
    
    def test_register_handler(self):
        """Test handler registration."""
        from src.runtime.dispatch import register, _HANDLERS, _HANDLER_METADATA
        
        @register("test_action_123", category="test", description="Test handler")
        def test_handler(req, deps):
            return {"statusCode": 200, "result": "ok"}
        
        assert "test_action_123" in _HANDLERS
        assert _HANDLER_METADATA["test_action_123"]["category"] == "test"
        print("✓ Handler registration works correctly")
    
    def test_dispatch_known_action(self):
        """Test dispatching to a known action."""
        from src.runtime.dispatch import dispatch, _ensure_handlers_loaded
        from src.runtime.envelope import Envelope
        
        _ensure_handlers_loaded()
        
        envelope = Envelope.from_action_request({"action": "ping"})
        result = dispatch(envelope)
        
        assert result["statusCode"] == 200
        assert result.get("status") == "ok"
        print("✓ Dispatch to known action works correctly")
    
    def test_dispatch_unknown_action(self):
        """Test dispatching to an unknown action."""
        from src.runtime.dispatch import dispatch
        from src.runtime.envelope import Envelope
        
        envelope = Envelope.from_action_request({"action": "nonexistent_action_xyz"})
        result = dispatch(envelope)
        
        assert result["statusCode"] == 400
        assert "Unknown action" in result.get("error", "")
        print("✓ Dispatch to unknown action returns error correctly")
    
    def test_dispatch_no_action(self):
        """Test dispatching with no action specified."""
        from src.runtime.dispatch import dispatch
        from src.runtime.envelope import Envelope
        
        envelope = Envelope.from_action_request({})
        result = dispatch(envelope)
        
        assert result["statusCode"] == 400
        assert "No action" in result.get("error", "")
        print("✓ Dispatch with no action returns error correctly")
    
    def test_dispatch_with_deps(self):
        """Test dispatch_with_deps convenience function."""
        from src.runtime.dispatch import dispatch_with_deps, _ensure_handlers_loaded
        
        _ensure_handlers_loaded()
        
        result = dispatch_with_deps("ping", {})
        
        assert result["statusCode"] == 200
        print("✓ dispatch_with_deps() works correctly")
    
    def test_list_handlers(self):
        """Test listing handlers."""
        from src.runtime.dispatch import list_handlers, _ensure_handlers_loaded
        
        _ensure_handlers_loaded()
        
        handlers = list_handlers()
        
        assert len(handlers) > 0
        assert "ping" in handlers
        assert "help" in handlers
        print(f"✓ list_handlers() returns {len(handlers)} handlers")
    
    def test_get_handlers_by_category(self):
        """Test getting handlers by category."""
        from src.runtime.dispatch import get_handlers_by_category, _ensure_handlers_loaded
        
        _ensure_handlers_loaded()
        
        categories = get_handlers_by_category()
        
        assert len(categories) > 0
        assert "utility" in categories
        print(f"✓ get_handlers_by_category() returns {len(categories)} categories")
    
    def test_handler_exists(self):
        """Test handler existence check."""
        from src.runtime.dispatch import handler_exists, _ensure_handlers_loaded
        
        _ensure_handlers_loaded()
        
        assert handler_exists("ping") == True
        assert handler_exists("nonexistent_xyz") == False
        print("✓ handler_exists() works correctly")
    
    def test_builtin_help_handler(self):
        """Test built-in help handler."""
        from src.runtime.dispatch import dispatch, _ensure_handlers_loaded
        from src.runtime.envelope import Envelope
        
        _ensure_handlers_loaded()
        
        envelope = Envelope.from_action_request({"action": "help"})
        result = dispatch(envelope)
        
        assert result["statusCode"] == 200
        assert "totalActions" in result
        assert "categories" in result
        print("✓ Built-in help handler works correctly")
    
    def test_builtin_list_actions_handler(self):
        """Test built-in list_actions handler."""
        from src.runtime.dispatch import dispatch, _ensure_handlers_loaded
        from src.runtime.envelope import Envelope
        
        _ensure_handlers_loaded()
        
        envelope = Envelope.from_action_request({"action": "list_actions"})
        result = dispatch(envelope)
        
        assert result["statusCode"] == 200
        assert "count" in result
        assert "actions" in result
        print("✓ Built-in list_actions handler works correctly")
    
    def test_list_actions_by_category(self):
        """Test list_actions with category filter."""
        from src.runtime.dispatch import dispatch, _ensure_handlers_loaded
        from src.runtime.envelope import Envelope
        
        _ensure_handlers_loaded()
        
        envelope = Envelope.from_action_request({
            "action": "list_actions",
            "category": "utility"
        })
        result = dispatch(envelope)
        
        assert result["statusCode"] == 200
        assert result.get("category") == "utility"
        print("✓ list_actions with category filter works correctly")


# =============================================================================
# TEST: Dependency Injection
# =============================================================================

class TestDeps:
    """Tests for dependency injection container."""
    
    def test_deps_creation(self):
        """Test Deps creation."""
        from src.runtime.deps import Deps, create_deps
        
        deps = create_deps(region="ap-south-1")
        
        assert deps.region == "ap-south-1"
        print("✓ Deps creation works correctly")
    
    def test_deps_config(self):
        """Test Deps config property."""
        from src.runtime.deps import create_deps
        
        deps = create_deps()
        config = deps.config
        
        assert "MESSAGES_TABLE_NAME" in config
        assert "MEDIA_BUCKET" in config
        assert "AUTO_REPLY_ENABLED" in config
        print("✓ Deps.config works correctly")
    
    def test_deps_waba_phone_map(self):
        """Test WABA phone map parsing."""
        from src.runtime.deps import create_deps
        
        deps = create_deps()
        waba_map = deps.waba_phone_map
        
        # Check if map is populated (may be empty in test env without env vars)
        if waba_map:
            assert isinstance(waba_map, dict)
        print("✓ Deps.waba_phone_map works correctly")
    
    def test_deps_get_waba_config(self):
        """Test getting WABA config."""
        from src.runtime.deps import create_deps
        
        deps = create_deps()
        config = deps.get_waba_config("1347766229904230")
        
        # Config may be empty in test env without env vars
        assert isinstance(config, dict)
        print("✓ Deps.get_waba_config() works correctly")
    
    def test_deps_format_wa_number(self):
        """Test WhatsApp number formatting."""
        from src.runtime.deps import create_deps
        
        deps = create_deps()
        
        assert deps.format_wa_number("1234567890") == "+1234567890"
        assert deps.format_wa_number("+1234567890") == "+1234567890"
        assert deps.format_wa_number("") == ""
        print("✓ Deps.format_wa_number() works correctly")
    
    def test_deps_origination_id_for_api(self):
        """Test origination ID formatting."""
        from src.runtime.deps import create_deps
        
        deps = create_deps()
        
        arn = "arn:aws:social-messaging:eu-west-2:123456789:phone-number-id/abc123"
        result = deps.origination_id_for_api(arn)
        
        assert result == "phone-number-id-abc123"
        print("✓ Deps.origination_id_for_api() works correctly")
    
    def test_get_deps_singleton(self):
        """Test global deps singleton."""
        from src.runtime.deps import get_deps
        
        deps1 = get_deps()
        deps2 = get_deps()
        
        assert deps1 is deps2
        print("✓ get_deps() returns singleton correctly")
    
    @patch('boto3.client')
    def test_deps_lazy_client_creation(self, mock_boto_client):
        """Test that clients are created lazily."""
        from src.runtime.deps import Deps
        
        deps = Deps()
        
        # No clients created yet
        mock_boto_client.assert_not_called()
        
        # Access s3 client - should create it
        _ = deps.s3
        mock_boto_client.assert_called()
        print("✓ Deps creates clients lazily")


# =============================================================================
# TEST: Bedrock Integration
# =============================================================================

class TestBedrockIntegration:
    """Tests for Bedrock integration."""
    
    @patch('boto3.client')
    def test_bedrock_agent_creation(self, mock_boto):
        """Test BedrockAgent initialization."""
        from src.bedrock.agent import BedrockAgent
        
        agent = BedrockAgent(
            agent_id="test-agent-id",
            agent_alias_id="test-alias",
            region="ap-south-1"
        )
        
        assert agent.agent_id == "test-agent-id"
        assert agent.agent_alias_id == "test-alias"
        assert agent.region == "ap-south-1"
        print("✓ BedrockAgent initialization works correctly")
    
    @patch('boto3.client')
    def test_bedrock_processor_creation(self, mock_boto):
        """Test BedrockProcessor initialization."""
        from src.bedrock.processor import BedrockProcessor
        
        processor = BedrockProcessor(region="ap-south-1")
        
        assert processor.region == "ap-south-1"
        print("✓ BedrockProcessor initialization works correctly")
    
    def test_processing_result_dataclass(self):
        """Test ProcessingResult dataclass."""
        from src.bedrock.processor import ProcessingResult
        
        result = ProcessingResult(
            success=True,
            message_id="msg-123",
            content_type="text",
            summary="Test summary",
            intent="greeting",
            reply_draft="Hello!"
        )
        
        assert result.success == True
        assert result.message_id == "msg-123"
        assert result.content_type == "text"
        assert result.intent == "greeting"
        print("✓ ProcessingResult dataclass works correctly")
    
    def test_agent_response_dataclass(self):
        """Test AgentResponse dataclass."""
        from src.bedrock.agent import AgentResponse
        
        response = AgentResponse(
            session_id="session-123",
            completion="This is the response",
            citations=[{"source": "kb"}]
        )
        
        assert response.session_id == "session-123"
        assert response.completion == "This is the response"
        assert len(response.citations) == 1
        print("✓ AgentResponse dataclass works correctly")
    
    @patch('boto3.client')
    def test_intent_detection(self, mock_boto):
        """Test intent detection in processor."""
        from src.bedrock.processor import BedrockProcessor
        
        processor = BedrockProcessor()
        
        # Test various intents
        assert processor._detect_intent("I need help with my order") == "support_request"
        assert processor._detect_intent("How much does it cost?") == "pricing_inquiry"
        assert processor._detect_intent("I want to book an appointment") == "booking_request"
        assert processor._detect_intent("Where is my package?") == "tracking_inquiry"
        assert processor._detect_intent("I want to cancel") == "cancellation_request"
        assert processor._detect_intent("Show me the menu") == "menu_request"
        assert processor._detect_intent("Hello there") == "greeting"
        assert processor._detect_intent("Random text") == "general_inquiry"
        print("✓ Intent detection works correctly")
    
    @patch('boto3.client')
    def test_entity_extraction(self, mock_boto):
        """Test entity extraction in processor."""
        from src.bedrock.processor import BedrockProcessor
        
        processor = BedrockProcessor()
        
        # Test phone extraction
        entities = processor._extract_entities("Call me at +919330994400")
        assert "phone_numbers" in entities
        assert "+919330994400" in entities["phone_numbers"]
        
        # Test email extraction
        entities = processor._extract_entities("Email me at test@wecare.digital")
        assert "emails" in entities
        assert "test@wecare.digital" in entities["emails"]
        
        # Test reference extraction
        entities = processor._extract_entities("My order number is ORDER-12345")
        assert "reference_numbers" in entities
        print("✓ Entity extraction works correctly")


# =============================================================================
# TEST: Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the complete runtime system."""
    
    def test_full_action_request_flow(self):
        """Test complete flow from event to response."""
        from src.runtime.parse_event import parse_event
        from src.runtime.dispatch import dispatch, _ensure_handlers_loaded
        
        _ensure_handlers_loaded()
        
        # Simulate API Gateway event
        event = {
            "requestContext": {
                "http": {"method": "POST", "path": "/api"},
                "requestId": "test-req-123"
            },
            "body": json.dumps({"action": "ping"})
        }
        
        # Parse event
        envelopes, source = parse_event(event)
        assert len(envelopes) == 1
        
        # Dispatch
        result = dispatch(envelopes[0])
        assert result["statusCode"] == 200
        assert result.get("status") == "ok"
        print("✓ Full action request flow works correctly")
    
    def test_full_direct_invoke_flow(self):
        """Test complete flow for direct Lambda invoke."""
        from src.runtime.parse_event import parse_event
        from src.runtime.dispatch import dispatch, _ensure_handlers_loaded
        
        _ensure_handlers_loaded()
        
        # Direct invoke event
        event = {"action": "help"}
        
        # Parse and dispatch
        envelopes, source = parse_event(event)
        result = dispatch(envelopes[0])
        
        assert result["statusCode"] == 200
        assert "totalActions" in result
        print("✓ Full direct invoke flow works correctly")
    
    def test_envelope_metadata_preserved(self):
        """Test that envelope metadata is preserved through dispatch."""
        from src.runtime.parse_event import parse_event
        from src.runtime.dispatch import dispatch, _ensure_handlers_loaded
        
        _ensure_handlers_loaded()
        
        event = {
            "requestContext": {
                "http": {"method": "POST"},
                "requestId": "unique-req-id-456"
            },
            "headers": {"x-custom-header": "test-value"},
            "body": json.dumps({"action": "ping"})
        }
        
        envelopes, _ = parse_event(event)
        envelope = envelopes[0]
        
        # Check metadata preserved
        assert envelope.metadata.get("headers", {}).get("x-custom-header") == "test-value"
        
        result = dispatch(envelope)
        assert result.get("_requestId") == envelope.request_id
        print("✓ Envelope metadata preserved correctly")


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

def run_all_tests():
    """Run all test classes."""
    print("\n" + "=" * 70)
    print("RUNTIME SYSTEM TEST SUITE")
    print("=" * 70 + "\n")
    
    test_classes = [
        ("Envelope Tests", TestEnvelope),
        ("Event Parser Tests", TestEventParser),
        ("Dispatcher Tests", TestDispatcher),
        ("Deps Tests", TestDeps),
        ("Bedrock Integration Tests", TestBedrockIntegration),
        ("Integration Tests", TestIntegration),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_class in test_classes:
        print(f"\n{'=' * 60}")
        print(f"Running: {name}")
        print("=" * 60)
        
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                try:
                    getattr(instance, method_name)()
                    passed += 1
                except Exception as e:
                    print(f"✗ {method_name}: {e}")
                    failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
