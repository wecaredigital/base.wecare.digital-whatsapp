#!/usr/bin/env python3
"""
Clear DynamoDB logs (MSG#, CONV#, MENU_SENT#, WELCOME_SENT#, EVENT#, EMAIL#)
Keep: CONFIG#, TEMPLATES#, QUALITY#, PAYMENT#, PROFILE#, FLOW#, etc.
"""

import boto3
import sys

TABLE_NAME = "base-wecare-digital-whatsapp"
REGION = "ap-south-1"
KEY_NAME = "base-wecare-digital-whatsapp"

# Prefixes to delete (logs/tracking)
DELETE_PREFIXES = ("MSG#", "CONV#", "MENU_SENT#", "WELCOME_SENT#", "EVENT#", "EMAIL#")

# Prefixes to KEEP (config/settings)
KEEP_PREFIXES = ("CONFIG#", "TEMPLATES#", "QUALITY#", "PAYMENT", "PROFILE#", "FLOW#", 
                 "TEMPLATE_", "THROUGHPUT#", "CHECKOUT_", "PRODUCT_", "META_")

def main():
    ddb = boto3.resource("dynamodb", region_name=REGION)
    table = ddb.Table(TABLE_NAME)
    
    print(f"Scanning {TABLE_NAME} for items to delete...")
    
    # Scan and collect items to delete
    items_to_delete = []
    items_to_keep = []
    
    scan_kwargs = {
        "ProjectionExpression": "#pk",
        "ExpressionAttributeNames": {"#pk": KEY_NAME}
    }
    
    while True:
        response = table.scan(**scan_kwargs)
        
        for item in response.get("Items", []):
            pk = item[KEY_NAME]
            
            # Check if should delete
            should_delete = False
            for prefix in DELETE_PREFIXES:
                if pk.startswith(prefix):
                    should_delete = True
                    break
            
            if should_delete:
                items_to_delete.append({KEY_NAME: pk})
            else:
                items_to_keep.append(pk)
        
        # Check for more pages
        if "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        else:
            break
    
    print(f"\nFound {len(items_to_delete)} items to DELETE")
    print(f"Found {len(items_to_keep)} items to KEEP")
    
    # Show what we're keeping
    print("\nItems to KEEP:")
    for pk in sorted(set(p.split("#")[0] + "#" for p in items_to_keep)):
        count = len([p for p in items_to_keep if p.startswith(pk)])
        print(f"  {pk}* : {count}")
    
    if not items_to_delete:
        print("\nNo items to delete!")
        return
    
    # Confirm
    confirm = input(f"\nDelete {len(items_to_delete)} items? (yes/no): ")
    if confirm.lower() != "yes":
        print("Aborted.")
        return
    
    # Batch delete (25 items per batch)
    deleted = 0
    batch_size = 25
    
    with table.batch_writer() as batch:
        for item in items_to_delete:
            batch.delete_item(Key=item)
            deleted += 1
            if deleted % 100 == 0:
                print(f"Deleted {deleted}/{len(items_to_delete)}...")
    
    print(f"\n✅ Deleted {deleted} items")
    
    # Verify
    response = table.scan(Select="COUNT")
    print(f"Remaining items: {response['Count']}")

if __name__ == "__main__":
    main()
