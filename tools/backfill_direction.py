"""Backfill direction field for existing DynamoDB items."""
import boto3

REGION = "ap-south-1"
TABLE = "base-wecare-digital-whatsapp"
PK_NAME = "base-wecare-digital-whatsapp"

ddb = boto3.resource("dynamodb", region_name=REGION)
table = ddb.Table(TABLE)

def backfill():
    inbound = 0
    outbound = 0
    skipped = 0
    
    # Scan all items
    response = table.scan()
    items = response.get("Items", [])
    
    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    
    print(f"Total items to process: {len(items)}")
    
    for item in items:
        pk = item.get(PK_NAME)
        item_type = item.get("itemType", "")
        has_direction = "direction" in item
        has_delivery_status = "deliveryStatus" in item
        has_from = "from" in item
        
        if has_direction:
            skipped += 1
            continue
        
        # Skip CONVERSATION items
        if item_type == "CONVERSATION":
            skipped += 1
            continue
        
        # Determine direction
        direction = "INBOUND"  # Default
        
        if item_type == "MESSAGE_STATUS":
            direction = "OUTBOUND"
        elif has_delivery_status and not has_from:
            # Status-only items are outbound
            direction = "OUTBOUND"
        elif item_type == "MESSAGE" and has_from:
            # MESSAGE items with 'from' are inbound
            direction = "INBOUND"
        
        # Update the item
        try:
            table.update_item(
                Key={PK_NAME: pk},
                UpdateExpression="SET direction = :dir",
                ExpressionAttributeValues={":dir": direction},
            )
            if direction == "INBOUND":
                inbound += 1
            else:
                outbound += 1
            print(".", end="", flush=True)
        except Exception as e:
            print(f"x", end="", flush=True)
    
    print()
    print(f"=== Backfill Complete ===")
    print(f"INBOUND updated: {inbound}")
    print(f"OUTBOUND updated: {outbound}")
    print(f"Skipped: {skipped}")

if __name__ == "__main__":
    backfill()
