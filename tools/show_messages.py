"""Show DynamoDB messages with direction."""
import boto3

ddb = boto3.resource('dynamodb', region_name='ap-south-1')
table = ddb.Table('base-wecare-digital-whatsapp')

response = table.scan()
items = response.get('Items', [])
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response.get('Items', []))

# Filter messages only (not conversations)
messages = [i for i in items if i.get('itemType') in ('MESSAGE', 'MESSAGE_STATUS')]

# Sort by timestamp
messages.sort(key=lambda x: x.get('receivedAt', x.get('deliveryStatusUpdatedAt', '')), reverse=True)

print('=' * 110)
print(f"{'Direction':<10} {'Type':<10} {'From/To':<15} {'Status':<12} {'Preview':<45} {'Time':<18}")
print('=' * 110)

for m in messages[:35]:  # Show last 35
    direction = m.get('direction', '?')
    mtype = m.get('type', m.get('itemType', '?'))[:9]
    
    if direction == 'INBOUND':
        from_to = m.get('from', '?')[:14]
    else:
        from_to = m.get('recipientId', '?')[:14]
    
    status = m.get('deliveryStatus', '-')[:11]
    preview = m.get('preview', m.get('textBody', ''))[:44] if m.get('preview') or m.get('textBody') else '[media]'
    preview = preview.replace('\n', ' ')
    
    time_str = m.get('receivedAt', m.get('deliveryStatusUpdatedAt', ''))
    if time_str:
        try:
            time_str = time_str[:16].replace('T', ' ')
        except:
            pass
    
    # Direction display
    dir_display = 'RECEIVED' if direction == 'INBOUND' else 'SENT'
    
    print(f"{dir_display:<10} {mtype:<10} {from_to:<15} {status:<12} {preview:<45} {time_str:<18}")

print('=' * 110)
print(f"Showing 35 of {len(messages)} messages")
print()

# Summary
inbound = len([i for i in messages if i.get('direction') == 'INBOUND'])
outbound = len([i for i in messages if i.get('direction') == 'OUTBOUND'])
print(f"Summary: {inbound} RECEIVED (inbound) | {outbound} SENT (outbound)")
