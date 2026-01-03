# AWS Kiro — Omni-Channel Messaging Spec

## Channels & Configuration

### WhatsApp (AWS End User Messaging Social)
- UK test number: **+447447840003**
- WABA ID: **1347766229904230** (WECARE.DIGITAL)
- Uses `originationPhoneNumberId` for sending

### SMS (AWS End User Messaging SMS / Pinpoint SMS Voice V2)
- Sender ID: **WDBEEP** (registered for India)
- Test number: **+919903300044**
- India DLT compliance: Add `IN_ENTITY_ID` and `IN_TEMPLATE_ID` if required

### Voice (Polly TTS + SMS fallback)
- Voice: **Aditi** (Indian English, standard engine)
- Audio stored in S3: `dev.wecare.digital/voice/`
- For India numbers: SMS sent with audio link

### Email (Amazon SES)
- FROM: **"WECARE.DIGITAL" <one@wecare.digital>**
- REPLY-TO: **one@wecare.digital**
- Default recipient: **manish@wecare.digital**

## Bedrock Agent Action Groups

| Action Group | Description | Lambda |
|-------------|-------------|--------|
| PaymentsAPI | Razorpay payment links | base-wecare-digital-whatsapp |
| ShortlinksAPI | Short URL creation | base-wecare-digital-whatsapp |
| WhatsAppAPI | WhatsApp messaging | base-wecare-digital-whatsapp |
| NotificationsAPI | SMS + Email | base-wecare-digital-whatsapp |
| VoiceAPI | Polly TTS + SMS | base-wecare-digital-whatsapp |

## Fallback Order
1. WhatsApp (if allowed)
2. SMS
3. Voice (urgent cases)
4. Email

## India Compliance (SMS)
When sending to India (+91) with Sender ID:
- Provide DLT Entity ID (`IN_ENTITY_ID`)
- Provide DLT Template ID (`IN_TEMPLATE_ID`)
- Message must match registered template exactly
