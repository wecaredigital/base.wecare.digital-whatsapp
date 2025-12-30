import boto3
import json

social = boto3.client('socialmessaging', region_name='ap-south-1')

to_number = '+447447840003'
origination_id = 'phone-number-id-0b0d77d6d54645d991db7aa9cf1b0eb2'

payload = {
    'messaging_product': 'whatsapp',
    'to': to_number,
    'type': 'text',
    'text': {'body': 'Test - bytes vs string format'}
}

# Test with BYTES (current Lambda code)
print("Test with .encode('utf-8') - BYTES:")
try:
    resp = social.send_whatsapp_message(
        originationPhoneNumberId=origination_id,
        metaApiVersion='v20.0',
        message=json.dumps(payload).encode('utf-8'),
    )
    print(f'SUCCESS! messageId: {resp.get("messageId")}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')

# Test with STRING
print("\nTest with STRING (no encode):")
try:
    resp = social.send_whatsapp_message(
        originationPhoneNumberId=origination_id,
        metaApiVersion='v20.0',
        message=json.dumps(payload),
    )
    print(f'SUCCESS! messageId: {resp.get("messageId")}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
