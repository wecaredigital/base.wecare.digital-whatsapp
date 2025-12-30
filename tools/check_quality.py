"""
Check WhatsApp Phone Number Quality Ratings.

Quality Ratings:
  🟢 GREEN  - High quality
  🟡 YELLOW - Medium quality (needs attention)
  🔴 RED    - Low quality (urgent action needed)

Phone Number Status:
  Connected  - Can send messages within quota
  Flagged    - Quality is low, needs improvement in 7 days
  Restricted - Reached 24-hour conversation limit
"""
import boto3
from datetime import datetime

REGION = "ap-south-1"
social = boto3.client('socialmessaging', region_name=REGION)


def get_quality_emoji(rating):
    """Get emoji for quality rating."""
    return {
        'GREEN': '🟢',
        'YELLOW': '🟡', 
        'RED': '🔴',
    }.get(rating, '⚪')


def check_all_phone_numbers():
    """Check quality rating for all linked WhatsApp phone numbers."""
    print("=" * 80)
    print("WhatsApp Phone Number Quality Report")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Get all linked WABA accounts
    response = social.list_linked_whatsapp_business_accounts()
    accounts = response.get('linkedAccounts', [])
    
    if not accounts:
        print("No linked WhatsApp Business Accounts found.")
        return
    
    for account in accounts:
        waba_id = account.get('id')
        waba_name = account.get('wabaName', 'Unknown')
        
        # Get detailed account info including phone numbers
        detail = social.get_linked_whatsapp_business_account(id=waba_id)
        account_detail = detail.get('account', {})
        phone_numbers = account_detail.get('phoneNumbers', [])
        
        print(f"\n📱 Business Account: {waba_name}")
        print(f"   WABA ID: {account.get('wabaId')}")
        print(f"   Status: {account.get('registrationStatus')}")
        print("-" * 60)
        
        for phone in phone_numbers:
            quality = phone.get('qualityRating', 'UNKNOWN')
            emoji = get_quality_emoji(quality)
            
            print(f"\n   Phone: {phone.get('displayPhoneNumber')}")
            print(f"   Display Name: {phone.get('displayPhoneNumberName')}")
            print(f"   Quality Rating: {emoji} {quality}")
            print(f"   Phone Number ID: {phone.get('phoneNumberId')}")
            print(f"   Meta Phone ID: {phone.get('metaPhoneNumberId')}")
            
            # Quality advice
            if quality == 'YELLOW':
                print("\n   ⚠️  WARNING: Quality is medium. Review recent messages.")
                print("   - Check for user blocks/reports")
                print("   - Ensure messages are relevant and expected")
                print("   - Avoid sending too many messages")
            elif quality == 'RED':
                print("\n   🚨 CRITICAL: Quality is low! Take immediate action.")
                print("   - Stop sending promotional messages")
                print("   - Review and improve message content")
                print("   - If not improved in 7 days, limits will be reduced")
    
    print("\n" + "=" * 80)
    print("Quality Rating Guide:")
    print("  🟢 GREEN  - High quality, all good!")
    print("  🟡 YELLOW - Medium quality, needs attention")
    print("  🔴 RED    - Low quality, urgent action needed")
    print("=" * 80)


if __name__ == '__main__':
    check_all_phone_numbers()
