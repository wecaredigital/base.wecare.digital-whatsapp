#!/usr/bin/env python3
# =============================================================================
# CLI Tool for WhatsApp Business API
# =============================================================================
# Developer/admin tooling for local testing and management.
# Uses the same dispatch system as Lambda handlers.
#
# Usage:
#   python tools/cli.py ping
#   python tools/cli.py list_actions
#   python tools/cli.py send_text --to +447447840003 --text "Hello"
#   python tools/cli.py --json '{"action": "ping"}'
# =============================================================================

import argparse
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.runtime.envelope import Envelope
from src.runtime.dispatch import dispatch
from src.runtime.deps import create_deps


def main():
    parser = argparse.ArgumentParser(
        description="WhatsApp Business API CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ping
  %(prog)s list_actions
  %(prog)s list_actions --category messaging
  %(prog)s send_text --metaWabaId 1347766229904230 --to +447447840003 --text "Hello"
  %(prog)s get_messages --metaWabaId 1347766229904230 --limit 10
  %(prog)s --json '{"action": "ping"}'
  %(prog)s --file request.json
        """
    )
    
    parser.add_argument("action", nargs="?", help="Action to execute")
    parser.add_argument("--json", "-j", help="JSON payload (overrides action)")
    parser.add_argument("--file", "-f", help="JSON file to load payload from")
    parser.add_argument("--pretty", "-p", action="store_true", help="Pretty print output")
    parser.add_argument("--region", "-r", default="ap-south-1", help="AWS region")
    
    # Common parameters
    parser.add_argument("--metaWabaId", help="Meta WABA ID")
    parser.add_argument("--tenantId", help="Tenant ID")
    parser.add_argument("--to", help="Recipient phone number")
    parser.add_argument("--text", help="Message text")
    parser.add_argument("--category", help="Category filter")
    parser.add_argument("--limit", type=int, help="Result limit")
    parser.add_argument("--templateName", help="Template name")
    parser.add_argument("--language", help="Language code")
    
    args = parser.parse_args()
    
    # Build payload
    payload = {}
    
    if args.file:
        with open(args.file, "r") as f:
            payload = json.load(f)
    elif args.json:
        payload = json.loads(args.json)
    elif args.action:
        payload = {"action": args.action}
        
        # Add optional parameters
        if args.metaWabaId:
            payload["metaWabaId"] = args.metaWabaId
        if args.tenantId:
            payload["tenantId"] = args.tenantId
        if args.to:
            payload["to"] = args.to
        if args.text:
            payload["text"] = args.text
        if args.category:
            payload["category"] = args.category
        if args.limit:
            payload["limit"] = args.limit
        if args.templateName:
            payload["templateName"] = args.templateName
        if args.language:
            payload["language"] = args.language
    else:
        parser.print_help()
        sys.exit(1)
    
    # Mark as CLI source
    payload["_source"] = "cli"
    
    # Create envelope and dispatch
    envelope = Envelope.from_action_request(payload, source="cli")
    deps = create_deps(region=args.region)
    
    result = dispatch(envelope, deps)
    
    # Output
    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(result, ensure_ascii=False, default=str))
    
    # Exit with appropriate code
    status_code = result.get("statusCode", 200)
    if status_code >= 400:
        sys.exit(1)


if __name__ == "__main__":
    main()
