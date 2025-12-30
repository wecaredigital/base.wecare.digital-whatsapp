import os
os.environ["MESSAGES_TABLE_NAME"] = "base-wecare-digital-whatsapp"
os.environ["MESSAGES_PK_NAME"] = "base-wecare-digital-whatsapp"
os.environ["MEDIA_BUCKET"] = "dev.wecare.digital"
os.environ["MEDIA_PREFIX"] = "WhatsApp/"
os.environ["META_API_VERSION"] = "v20.0"
os.environ["AUTO_REPLY_ENABLED"] = "true"
os.environ["AUTO_REPLY_TEXT"] = "Test"
os.environ["ECHO_MEDIA_BACK"] = "true"
os.environ["MARK_AS_READ_ENABLED"] = "true"
os.environ["REACT_EMOJI_ENABLED"] = "true"
os.environ["FORWARD_ENABLED"] = "false"
os.environ["FORWARD_TO_WA_ID"] = ""
os.environ["EMAIL_NOTIFICATION_ENABLED"] = "true"
os.environ["EMAIL_SNS_TOPIC_ARN"] = "arn:aws:sns:ap-south-1:010526260063:base-wecare-digital"
os.environ["WABA_PHONE_MAP_JSON"] = '{"1347766229904230":{"businessAccountName":"WECARE.DIGITAL","phoneArn":"arn:aws:social-messaging:ap-south-1:010526260063:phone-number-id/3f8934395ae24a4583a413087a3d3fb0","phone":"+91 93309 94400","meta_phone_number_id":"831049713436137"},"1390647332755815":{"businessAccountName":"Manish Agarwal","phoneArn":"arn:aws:social-messaging:ap-south-1:010526260063:phone-number-id/0b0d77d6d54645d991db7aa9cf1b0eb2","phone":"+91 99033 00044","meta_phone_number_id":"888782840987368"}}'

import logging
logging.basicConfig(level=logging.INFO)

from app import handle_send_text, format_wa_number, origination_id_for_api, WABA_PHONE_MAP

print(f"WABA_PHONE_MAP: {WABA_PHONE_MAP}")

meta_waba_id = "1390647332755815"
to_number = "+447447840003"

waba_config = WABA_PHONE_MAP.get(meta_waba_id, {})
phone_arn = waba_config.get("phoneArn", "")

print(f"waba_config: {waba_config}")
print(f"phone_arn: {phone_arn}")

formatted_to = format_wa_number(to_number)
origination_id = origination_id_for_api(phone_arn)

print(f"formatted_to: {formatted_to}")
print(f"origination_id: {origination_id}")

# Now test the actual send
import boto3
import json

social = boto3.client('socialmessaging', region_name='ap-south-1')

payload = {
    "messaging_product": "whatsapp",
    "to": formatted_to,
    "type": "text",
    "text": {"body": "Direct test"},
}

print(f"payload: {json.dumps(payload)}")

try:
    response = social.send_whatsapp_message(
        originationPhoneNumberId=origination_id,
        metaApiVersion="v20.0",
        message=json.dumps(payload),
    )
    print(f"SUCCESS: {response}")
except Exception as e:
    print(f"ERROR: {e}")
