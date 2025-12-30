import boto3
import json

social = boto3.client('socialmessaging', region_name='ap-south-1')

# Test with UK number that has 24h window
to_number = '+447447840003'

# Test 1: From Manish Agarwal
print("=" * 50)
print("Test 1: From Manish Agarwal (+91 99033 00044)")
origination_id1 = 'phone-number-id-0b0d77d6d54645d991db7aa9cf1b0eb2'

payload1 = {
    'messaging_product': 'whatsapp',
    'to': to_number,
    'type': 'text',
    'text': {'body': 'Test from Manish Agarwal - WECARE.DIGITAL Lambda v38'}
}

try:
    resp = social.send_whatsapp_message(
        originationPhoneNumberId=origination_id1,
        metaApiVersion='v20.0',
        message=json.dumps(payload1).encode('utf-8'),
    )
    print(f'SUCCESS! messageId: {resp.get("messageId")}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')

# Test 2: From WECARE.DIGITAL
print("\n" + "=" * 50)
print("Test 2: From WECARE.DIGITAL (+91 93309 94400)")
origination_id2 = 'phone-number-id-3f8934395ae24a4583a413087a3d3fb0'

payload2 = {
    'messaging_product': 'whatsapp',
    'to': to_number,
    'type': 'text',
    'text': {'body': 'Test from WECARE.DIGITAL - Lambda v38'}
}

try:
    resp = social.send_whatsapp_message(
        originationPhoneNumberId=origination_id2,
        metaApiVersion='v20.0',
        message=json.dumps(payload2).encode('utf-8'),
    )
    print(f'SUCCESS! messageId: {resp.get("messageId")}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
