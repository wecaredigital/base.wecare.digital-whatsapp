import boto3
from datetime import datetime, timedelta

ddb = boto3.resource('dynamodb', region_name='ap-south-1')
table = ddb.Table('base-wecare-digital-whatsapp')

# Scan for recent inbound messages
response = table.scan(
    FilterExpression='itemType = :t AND direction = :d',
    ExpressionAttributeValues={':t': 'MESSAGE', ':d': 'INBOUND'},
    ProjectionExpression='#from, receivedAt, originationPhoneNumberId, wabaId',
    ExpressionAttributeNames={'#from': 'from'},
    Limit=10
)

print('Recent inbound messages:')
for item in response.get('Items', []):
    print(f"  From: {item.get('from')}, WABA: {item.get('wabaId')}, Received: {item.get('receivedAt')}, Phone: {item.get('originationPhoneNumberId')}")
