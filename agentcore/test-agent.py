#!/usr/bin/env python3
"""Test Bedrock Agent with all action groups."""
import boto3
import json
import uuid

AGENT_ID = "UFVSBWGCIU"
AGENT_ALIAS_ID = "TSTALIASID"
REGION = "ap-south-1"

def test_agent(prompt: str, session_id: str = None):
    """Invoke the agent with a prompt."""
    client = boto3.client("bedrock-agent-runtime", region_name=REGION)
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    response = client.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=prompt
    )
    
    # Process streaming response
    result = ""
    for event in response.get("completion", []):
        if "chunk" in event:
            result += event["chunk"].get("bytes", b"").decode()
    
    return result, session_id

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("WECARE.DIGITAL - Bedrock Agent Multi-Channel Test")
    print("=" * 60)
    
    # Check for specific test
    test_type = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if test_type in ["sms", "all"]:
        # Test SMS to India number
        print("\n[SMS] Sending SMS to +919903300044...")
        result, _ = test_agent("Send an SMS to +919903300044 with message: Hello from WECARE.DIGITAL! Your appointment is confirmed for tomorrow at 10 AM.")
        print(result)
    
    if test_type in ["email", "all"]:
        # Test Email
        print("\n[EMAIL] Sending Email to manish@wecare.digital...")
        result, _ = test_agent("Send an email to manish@wecare.digital with subject 'Test from Bedrock Agent' and body 'Hello! This is a test email sent via the Bedrock Agent NotificationsAPI.'")
        print(result)
    
    if test_type in ["voice", "all"]:
        # Test Voice call
        print("\n[VOICE] Initiating Voice call to +919903300044...")
        result, _ = test_agent("Make a voice call to +919903300044 with message: Hello! This is a test call from WECARE.DIGITAL. Your appointment is confirmed.")
        print(result)
    
    if test_type in ["whatsapp", "all"]:
        # Test WhatsApp (UK test number)
        print("\n[WHATSAPP] Sending WhatsApp to +447447840003...")
        result, _ = test_agent("Send a WhatsApp text message to +447447840003 saying: Hello! This is a test from WECARE.DIGITAL Bedrock Agent.")
        print(result)
    
    if test_type in ["payment", "all"]:
        # Test Payment Link
        print("\n[PAYMENT] Creating Payment Link (Rs. 500)...")
        result, _ = test_agent("Create a payment link for Rs. 500 for consultation fee")
        print(result)
    
    if test_type in ["shortlink", "all"]:
        # Test Short Link
        print("\n[SHORTLINK] Creating Short Link...")
        result, _ = test_agent("Create a short link for https://wecare.digital/services with title Services Page")
        print(result)
    
    if test_type in ["combined", "all"]:
        # Combined multi-channel test
        print("\n[COMBINED] Multi-channel notification test...")
        result, _ = test_agent(
            "Create a payment link for Rs. 1000 for premium consultation, "
            "then send the payment link via WhatsApp to +447447840003, "
            "also send an SMS to +919903300044 with the payment link, "
            "and send an email to manish@wecare.digital with the payment details"
        )
        print(result)
    
    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
