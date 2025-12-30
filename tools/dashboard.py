"""
WhatsApp Message Dashboard - Detailed viewer for DynamoDB messages.
Usage:
    python dashboard.py                    # Show all messages
    python dashboard.py --direction INBOUND   # Filter by direction
    python dashboard.py --from 447447840003   # Filter by sender
    python dashboard.py --conversation CONV#xxx  # Filter by conversation
    python dashboard.py --type image          # Filter by message type
    python dashboard.py --status delivered    # Filter by delivery status
    python dashboard.py --detail MSG#wamid... # Show full detail for one message
    python dashboard.py --stats               # Show statistics only
"""
import argparse
import boto3
from datetime import datetime
from collections import defaultdict

# Config
TABLE_NAME = "base-wecare-digital-whatsapp"
REGION = "ap-south-1"

ddb = boto3.resource('dynamodb', region_name=REGION)
table = ddb.Table(TABLE_NAME)


def scan_all_items():
    """Scan all items from table."""
    items = []
    response = table.scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items


def format_time(ts):
    """Format timestamp for display."""
    if not ts:
        return "-"
    try:
        return ts[:19].replace('T', ' ')
    except:
        return str(ts)[:19]


def truncate(s, length=40):
    """Truncate string with ellipsis."""
    if not s:
        return ""
    s = str(s).replace('\n', ' ').replace('\r', '')
    return s[:length] + "..." if len(s) > length else s


def print_separator(char='=', width=140):
    print(char * width)


def print_header():
    print_separator()
    print(f"{'Dir':<8} {'Type':<10} {'From/To':<15} {'Status':<10} {'Read':<5} {'React':<6} {'Preview':<40} {'Time':<20}")
    print_separator('-')


def print_message_row(m):
    """Print a single message row."""
    direction = m.get('direction', '?')
    dir_display = 'IN' if direction == 'INBOUND' else 'OUT' if direction == 'OUTBOUND' else '?'
    
    mtype = m.get('type', m.get('itemType', '?'))[:9]
    
    if direction == 'INBOUND':
        from_to = m.get('from', '?')[:14]
    else:
        from_to = m.get('recipientId', m.get('to', '?'))[:14]
    
    status = m.get('deliveryStatus', '-')[:9]
    
    marked_read = '✓' if m.get('markedAsRead') else '-'
    reacted = m.get('reactedWithEmoji', '-')[:5] if m.get('reactedWithEmoji') else '-'
    
    preview = m.get('preview', m.get('textBody', ''))
    if not preview and m.get('type') in ('image', 'video', 'audio', 'document', 'sticker'):
        preview = f"[{m.get('type')}]"
    preview = truncate(preview, 39)
    
    time_str = format_time(m.get('receivedAt', m.get('deliveryStatusUpdatedAt', '')))
    
    print(f"{dir_display:<8} {mtype:<10} {from_to:<15} {status:<10} {marked_read:<5} {reacted:<6} {preview:<40} {time_str:<20}")


def print_message_detail(m):
    """Print full detail for a single message."""
    print_separator('=')
    print(f"MESSAGE DETAIL: {m.get('base-wecare-digital-whatsapp', 'Unknown')}")
    print_separator('=')
    
    # Group fields
    core_fields = ['base-wecare-digital-whatsapp', 'itemType', 'direction', 'type']
    sender_fields = ['from', 'to', 'senderName', 'fromPk', 'recipientId']
    content_fields = ['textBody', 'preview', 'caption', 'filename', 'mimeType']
    media_fields = ['mediaId', 's3Bucket', 's3Key', 's3Uri']
    status_fields = ['deliveryStatus', 'deliveryStatusTimestamp', 'deliveryStatusHistory', 
                     'markedAsRead', 'markedAsReadAt', 'reactedWithEmoji', 'reactedAt']
    meta_fields = ['receivedAt', 'waTimestamp', 'conversationPk', 'originationPhoneNumberId',
                   'wabaMetaId', 'businessAccountName', 'businessPhone', 'meta_phone_number_id',
                   'snsMessageId', 'snsTopicArn']
    
    def print_section(title, fields):
        print(f"\n{title}:")
        print("-" * 60)
        for f in fields:
            if f in m and m[f]:
                val = m[f]
                if isinstance(val, list):
                    print(f"  {f}:")
                    for i, item in enumerate(val):
                        print(f"    [{i}] {item}")
                else:
                    print(f"  {f}: {val}")
    
    print_section("Core", core_fields)
    print_section("Sender/Recipient", sender_fields)
    print_section("Content", content_fields)
    print_section("Media", media_fields)
    print_section("Status & Actions", status_fields)
    print_section("Metadata", meta_fields)
    
    # Any remaining fields
    shown = set(core_fields + sender_fields + content_fields + media_fields + status_fields + meta_fields)
    remaining = [k for k in m.keys() if k not in shown]
    if remaining:
        print_section("Other", remaining)
    
    print_separator('=')


def print_quality_ratings(items):
    """Print phone quality ratings and throughput info."""
    quality_items = [i for i in items if i.get('itemType') == 'PHONE_QUALITY']
    
    if not quality_items:
        print("\nNo quality rating data found yet.")
        print("Quality ratings are tracked when messages are processed.")
        return
    
    print_separator('=')
    print("PHONE NUMBER QUALITY & THROUGHPUT")
    print_separator('=')
    
    for q in quality_items:
        rating = q.get('qualityRating', 'UNKNOWN')
        emoji = {'GREEN': '🟢', 'YELLOW': '🟡', 'RED': '🔴'}.get(rating, '⚪')
        default_mps = q.get('throughputDefaultMps', 80)
        max_mps = q.get('throughputMaxMps', 1000)
        status = q.get('throughputStatus', 'UNKNOWN')
        eligible = q.get('throughputEligibleForIncrease', False)
        note = q.get('throughputNote', '')
        
        print(f"\n{emoji} {q.get('displayName', 'Unknown')} ({q.get('businessName', '')})")
        print(f"   Phone: {q.get('phoneNumber', 'Unknown')}")
        print(f"   Quality Rating: {rating}")
        print(f"   Throughput: {default_mps} MPS (default) | {max_mps} MPS (max)")
        print(f"   Throughput Status: {status}")
        if eligible:
            print(f"   ✅ Eligible for throughput increase")
        else:
            print(f"   ❌ Not eligible for throughput increase")
        if note:
            print(f"   📝 {note}")
        print(f"   Last Checked: {format_time(q.get('lastCheckedAt', ''))}")
        
        # Show history if available
        history = q.get('qualityHistory', [])
        if history and len(history) > 1:
            print(f"   History ({len(history)} checks):")
            for h in history[-5:]:  # Show last 5
                h_status = h.get('throughputStatus', h.get('throughputMps', '80 MPS'))
                print(f"      {h.get('rating', '?')} | {h_status} - {format_time(h.get('checkedAt', ''))}")
    
    print("\n" + "-" * 60)
    print("Throughput Info:")
    print("  Default: 80 MPS | Max: 1,000 MPS")
    print("  Requirements for 1,000 MPS increase:")
    print("    1. Quality rating: GREEN or YELLOW")
    print("    2. Unlimited business-initiated conversations tier")
    print("    3. Contact Meta support to request increase")
    print("  Note: Actual MPS is managed by Meta, not exposed via API")
    print_separator('=')


def print_infrastructure(items):
    """Print infrastructure configuration (VPC endpoint, service-linked role)."""
    config_items = [i for i in items if i.get('itemType') == 'INFRASTRUCTURE_CONFIG']
    
    if not config_items:
        print("\nNo infrastructure config data found yet.")
        print("Infrastructure config is tracked when messages are processed.")
        return
    
    print_separator('=')
    print("INFRASTRUCTURE CONFIGURATION")
    print_separator('=')
    
    for c in config_items:
        region = c.get('region', 'unknown')
        print(f"\nRegion: {region}")
        print(f"Last Checked: {format_time(c.get('lastCheckedAt', ''))}")
        
        # VPC Endpoint
        print(f"\n📡 VPC Endpoint (AWS PrivateLink):")
        print(f"   Service: {c.get('vpcEndpointServiceName', 'N/A')}")
        vpc_configured = c.get('vpcEndpointConfigured', False)
        vpc_count = c.get('vpcEndpointCount', 0)
        if vpc_configured:
            print(f"   Status: ✅ Configured ({vpc_count} endpoint(s))")
            for ep in c.get('vpcEndpoints', []):
                print(f"      - {ep.get('vpcEndpointId')} | VPC: {ep.get('vpcId')} | State: {ep.get('state')}")
                print(f"        Private DNS: {ep.get('privateDnsEnabled')}")
        else:
            print(f"   Status: ❌ Not configured")
            print(f"   Benefit: Private connection without internet gateway, lower latency")
        
        # Service-Linked Role
        print(f"\n🔐 Service-Linked Role:")
        slr_configured = c.get('serviceLinkedRoleConfigured', False)
        if slr_configured:
            slr = c.get('serviceLinkedRole', {})
            print(f"   Status: ✅ Configured")
            print(f"   Role: {slr.get('roleName', 'N/A')}")
            print(f"   ARN: {slr.get('roleArn', 'N/A')}")
        else:
            print(f"   Status: ❌ Not found")
            print(f"   Note: Created automatically when WABA is linked")
        
        # Recommendations
        recommendations = c.get('recommendations', [])
        if recommendations:
            print(f"\n💡 Recommendations:")
            for rec in recommendations:
                print(f"   [{rec.get('priority', 'INFO')}] {rec.get('message', '')}")
    
    print_separator('=')


def print_media_types(items):
    """Print supported media types configuration."""
    config_items = [i for i in items if i.get('itemType') == 'MEDIA_TYPES_CONFIG']
    
    if not config_items:
        print("\nNo media types config data found yet.")
        print("Media types config is stored when messages are processed.")
        return
    
    print_separator('=')
    print("WHATSAPP SUPPORTED MEDIA TYPES")
    print_separator('=')
    
    for c in config_items:
        print(f"\nLast Updated: {format_time(c.get('lastUpdatedAt', ''))}")
        print(f"Total Formats: {c.get('totalFormats', 0)}")
        print(f"Total MIME Types: {c.get('totalMimeTypes', 0)}")
        
        # Size limits
        limits = c.get('sizeLimits', {})
        print(f"\n📏 Size Limits:")
        print(f"   Audio:    {limits.get('audio', {}).get('maxMB', 'N/A')} MB")
        print(f"   Document: {limits.get('document', {}).get('maxMB', 'N/A')} MB")
        print(f"   Image:    {limits.get('image', {}).get('maxMB', 'N/A')} MB")
        print(f"   Sticker:  {limits.get('sticker', {}).get('maxKB', 'N/A')} KB")
        print(f"   Video:    {limits.get('video', {}).get('maxMB', 'N/A')} MB")
        
        # Media types by category
        media_types = c.get('mediaTypes', {})
        
        print(f"\n🎵 Audio Formats:")
        for fmt in media_types.get('audio', {}).get('formats', []):
            print(f"   {fmt.get('type'):<15} {fmt.get('extension'):<8} {fmt.get('mimeType'):<20} {fmt.get('maxSizeMB')} MB")
        
        print(f"\n📄 Document Formats:")
        for fmt in media_types.get('document', {}).get('formats', []):
            print(f"   {fmt.get('type'):<20} {fmt.get('extension'):<8} {fmt.get('maxSizeMB')} MB")
        
        print(f"\n🖼️ Image Formats:")
        for fmt in media_types.get('image', {}).get('formats', []):
            print(f"   {fmt.get('type'):<15} {fmt.get('extension'):<8} {fmt.get('mimeType'):<20} {fmt.get('maxSizeMB')} MB")
        note = media_types.get('image', {}).get('note', '')
        if note:
            print(f"   Note: {note}")
        
        print(f"\n🎭 Sticker Formats:")
        for fmt in media_types.get('sticker', {}).get('formats', []):
            max_size = fmt.get('maxSizeKB', fmt.get('maxSizeMB', 0) * 1024)
            print(f"   {fmt.get('type'):<20} {fmt.get('extension'):<8} {max_size} KB")
        note = media_types.get('sticker', {}).get('note', '')
        if note:
            print(f"   Note: {note}")
        
        print(f"\n🎬 Video Formats:")
        for fmt in media_types.get('video', {}).get('formats', []):
            print(f"   {fmt.get('type'):<15} {fmt.get('extension'):<8} {fmt.get('mimeType'):<20} {fmt.get('maxSizeMB')} MB")
        note = media_types.get('video', {}).get('note', '')
        if note:
            print(f"   Note: {note}")
        
        # Notes
        notes = c.get('notes', {})
        if notes:
            print(f"\n📝 Important Notes:")
            for key, note in notes.items():
                print(f"   {key}: {note}")
    
    print_separator('=')


def print_templates(items):
    """Print message templates configuration."""
    template_items = [i for i in items if i.get('itemType') == 'MESSAGE_TEMPLATES']
    
    if not template_items:
        print("\nNo message templates data found yet.")
        print("Templates are synced when messages are processed.")
        return
    
    print_separator('=')
    print("WHATSAPP MESSAGE TEMPLATES")
    print_separator('=')
    
    for t in template_items:
        print(f"\n📋 {t.get('businessName', 'Unknown')} (WABA: {t.get('wabaMetaId', 'N/A')})")
        print(f"   Last Updated: {format_time(t.get('lastUpdatedAt', ''))}")
        print(f"   Total Templates: {t.get('templateCount', 0)}")
        
        # Stats
        stats = t.get('stats', {})
        print(f"\n   📊 Status Summary:")
        print(f"      ✅ Approved: {stats.get('approved', 0)}")
        print(f"      ⏳ Pending:  {stats.get('pending', 0)}")
        print(f"      ❌ Rejected: {stats.get('rejected', 0)}")
        print(f"      ⏸️ Paused:   {stats.get('paused', 0)}")
        print(f"      🚫 Disabled: {stats.get('disabled', 0)}")
        
        # By category
        by_cat = stats.get('byCategory', {})
        print(f"\n   📁 By Category:")
        print(f"      Marketing:      {by_cat.get('MARKETING', 0)}")
        print(f"      Utility:        {by_cat.get('UTILITY', 0)}")
        print(f"      Authentication: {by_cat.get('AUTHENTICATION', 0)}")
        
        # By quality
        by_qual = stats.get('byQuality', {})
        print(f"\n   🎯 By Quality:")
        print(f"      🟢 Green:   {by_qual.get('GREEN', 0)}")
        print(f"      🟡 Yellow:  {by_qual.get('YELLOW', 0)}")
        print(f"      🔴 Red:     {by_qual.get('RED', 0)}")
        print(f"      ⚪ Unknown: {by_qual.get('UNKNOWN', 0)}")
        
        # By language
        by_lang = stats.get('byLanguage', {})
        if by_lang:
            print(f"\n   🌐 By Language:")
            for lang, count in sorted(by_lang.items()):
                print(f"      {lang}: {count}")
        
        # List templates
        templates = t.get('templates', [])
        if templates:
            print(f"\n   📝 Templates ({len(templates)}):")
            for tmpl in templates[:20]:  # Show first 20
                status_emoji = {
                    'APPROVED': '✅', 'PENDING': '⏳', 'REJECTED': '❌',
                    'PAUSED': '⏸️', 'DISABLED': '🚫'
                }.get(tmpl.get('templateStatus', ''), '❓')
                qual_emoji = {
                    'GREEN': '🟢', 'YELLOW': '🟡', 'RED': '🔴', 'UNKNOWN': '⚪'
                }.get(tmpl.get('templateQualityScore', ''), '⚪')
                print(f"      {status_emoji} {qual_emoji} {tmpl.get('templateName', 'N/A'):<30} [{tmpl.get('templateLanguage', '')}] {tmpl.get('templateCategory', '')}")
            
            if len(templates) > 20:
                print(f"      ... and {len(templates) - 20} more")
    
    # Reference info
    print(f"\n" + "-" * 60)
    print("Template Status Reference:")
    print("  ✅ APPROVED - Ready to use")
    print("  ⏳ PENDING  - Under Meta review (24-48 hours)")
    print("  ❌ REJECTED - Check rejection reason, resubmit")
    print("  ⏸️ PAUSED   - Quality issues, improve to resume")
    print("  🚫 DISABLED - Cannot be used")
    print("\nTemplate Categories:")
    print("  MARKETING      - Promotions, offers, announcements")
    print("  UTILITY        - Order updates, shipping, appointments")
    print("  AUTHENTICATION - OTP, verification codes")
    print_separator('=')


def print_statistics(items):
    """Print statistics about messages."""
    messages = [i for i in items if i.get('itemType') in ('MESSAGE', 'MESSAGE_STATUS')]
    conversations = [i for i in items if i.get('itemType') == 'CONVERSATION']
    quality_items = [i for i in items if i.get('itemType') == 'PHONE_QUALITY']
    
    print_separator('=')
    print("MESSAGE STATISTICS")
    print_separator('=')
    
    # Direction counts
    inbound = len([m for m in messages if m.get('direction') == 'INBOUND'])
    outbound = len([m for m in messages if m.get('direction') == 'OUTBOUND'])
    print(f"\nDirection:")
    print(f"  INBOUND (received):  {inbound}")
    print(f"  OUTBOUND (sent):     {outbound}")
    print(f"  Total messages:      {len(messages)}")
    print(f"  Conversations:       {len(conversations)}")
    
    # Type counts
    type_counts = defaultdict(int)
    for m in messages:
        type_counts[m.get('type', m.get('itemType', 'unknown'))] += 1
    print(f"\nMessage Types:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<15} {c}")
    
    # Status counts (for outbound)
    status_counts = defaultdict(int)
    for m in messages:
        if m.get('deliveryStatus'):
            status_counts[m.get('deliveryStatus')] += 1
    if status_counts:
        print(f"\nDelivery Status:")
        for s, c in sorted(status_counts.items(), key=lambda x: -x[1]):
            print(f"  {s:<15} {c}")
    
    # Read receipts sent
    read_sent = len([m for m in messages if m.get('markedAsRead')])
    print(f"\nRead Receipts Sent: {read_sent}")
    
    # Reactions sent
    reacted = len([m for m in messages if m.get('reactedWithEmoji')])
    emoji_counts = defaultdict(int)
    for m in messages:
        if m.get('reactedWithEmoji'):
            emoji_counts[m.get('reactedWithEmoji')] += 1
    print(f"Reactions Sent: {reacted}")
    if emoji_counts:
        for e, c in sorted(emoji_counts.items(), key=lambda x: -x[1]):
            print(f"  {e} x{c}")
    
    # Unique senders
    senders = set(m.get('from') for m in messages if m.get('from') and m.get('direction') == 'INBOUND')
    print(f"\nUnique Senders: {len(senders)}")
    for s in sorted(senders):
        print(f"  {s}")
    
    # Business accounts
    accounts = set(m.get('businessAccountName') for m in messages if m.get('businessAccountName'))
    print(f"\nBusiness Accounts: {len(accounts)}")
    for a in sorted(accounts):
        print(f"  {a}")
    
    # Media stats
    media_msgs = [m for m in messages if m.get('s3Uri')]
    print(f"\nMedia Downloaded: {len(media_msgs)}")
    
    # Time range
    times = [m.get('receivedAt') for m in messages if m.get('receivedAt')]
    if times:
        times.sort()
        print(f"\nTime Range:")
        print(f"  First: {format_time(times[0])}")
        print(f"  Last:  {format_time(times[-1])}")
    
    # Quality ratings
    if quality_items:
        print(f"\nPhone Quality & Throughput:")
        for q in quality_items:
            rating = q.get('qualityRating', 'UNKNOWN')
            emoji = {'GREEN': '🟢', 'YELLOW': '🟡', 'RED': '🔴'}.get(rating, '⚪')
            status = q.get('throughputStatus', 'UNKNOWN')
            print(f"  {emoji} {q.get('displayName', 'Unknown')}: {rating} | {status}")
    
    print_separator('=')


def main():
    parser = argparse.ArgumentParser(description='WhatsApp Message Dashboard')
    parser.add_argument('--direction', '-d', choices=['INBOUND', 'OUTBOUND'], help='Filter by direction')
    parser.add_argument('--from', '-f', dest='from_number', help='Filter by sender number')
    parser.add_argument('--to', '-t', help='Filter by recipient number')
    parser.add_argument('--conversation', '-c', help='Filter by conversation PK')
    parser.add_argument('--type', '-y', help='Filter by message type (text, image, video, etc.)')
    parser.add_argument('--status', '-s', help='Filter by delivery status')
    parser.add_argument('--detail', help='Show full detail for a message PK')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--quality', '-q', action='store_true', help='Show phone quality ratings')
    parser.add_argument('--infra', '-i', action='store_true', help='Show infrastructure config (VPC endpoint, service-linked role)')
    parser.add_argument('--media', '-m', action='store_true', help='Show supported media types')
    parser.add_argument('--templates', action='store_true', help='Show message templates')
    parser.add_argument('--limit', '-l', type=int, default=50, help='Limit number of messages (default: 50)')
    args = parser.parse_args()
    
    # Fetch all items
    print("Fetching messages from DynamoDB...")
    items = scan_all_items()
    
    # Show detail for single message
    if args.detail:
        for item in items:
            if item.get('base-wecare-digital-whatsapp') == args.detail:
                print_message_detail(item)
                return
        print(f"Message not found: {args.detail}")
        return
    
    # Show statistics
    if args.stats:
        print_statistics(items)
        return
    
    # Show quality ratings
    if args.quality:
        print_quality_ratings(items)
        return
    
    # Show infrastructure config
    if args.infra:
        print_infrastructure(items)
        return
    
    # Show media types
    if args.media:
        print_media_types(items)
        return
    
    # Show templates
    if args.templates:
        print_templates(items)
        return
    
    # Filter messages (exclude conversations for list view)
    messages = [i for i in items if i.get('itemType') in ('MESSAGE', 'MESSAGE_STATUS')]
    
    # Apply filters
    if args.direction:
        messages = [m for m in messages if m.get('direction') == args.direction]
    if args.from_number:
        messages = [m for m in messages if args.from_number in str(m.get('from', ''))]
    if args.to:
        messages = [m for m in messages if args.to in str(m.get('to', '') or m.get('recipientId', ''))]
    if args.conversation:
        messages = [m for m in messages if args.conversation in str(m.get('conversationPk', ''))]
    if args.type:
        messages = [m for m in messages if m.get('type') == args.type]
    if args.status:
        messages = [m for m in messages if m.get('deliveryStatus') == args.status]
    
    # Sort by time (newest first)
    messages.sort(key=lambda x: x.get('receivedAt', x.get('deliveryStatusUpdatedAt', '')), reverse=True)
    
    # Display
    total = len(messages)
    messages = messages[:args.limit]
    
    print(f"\nShowing {len(messages)} of {total} messages")
    print_header()
    
    for m in messages:
        print_message_row(m)
    
    print_separator('-')
    print(f"Showing {len(messages)} of {total} messages | Use --stats for statistics | Use --detail MSG#... for full detail")
    print_separator('=')


if __name__ == '__main__':
    main()
