# Clear DynamoDB logs (MSG#, CONV#, MENU_SENT#, WELCOME_SENT#)
# Keep: CONFIG#, TEMPLATES#, QUALITY#, etc.

$TableName = "base-wecare-digital-whatsapp"
$Region = "ap-south-1"
$KeyName = "base-wecare-digital-whatsapp"

# Prefixes to delete (logs/tracking)
$DeletePrefixes = @("MSG#", "CONV#", "MENU_SENT#", "WELCOME_SENT#", "EVENT#", "EMAIL#")

Write-Host "Scanning table for items to delete..." -ForegroundColor Yellow

$ExclusiveStartKey = $null
$TotalDeleted = 0
$BatchSize = 25

do {
    $ScanParams = @{
        TableName = $TableName
        ProjectionExpression = "#pk"
        ExpressionAttributeNames = @{ "#pk" = $KeyName }
    }
    
    if ($ExclusiveStartKey) {
        $ScanParams.ExclusiveStartKey = $ExclusiveStartKey
    }
    
    $Result = aws dynamodb scan --table-name $TableName `
        --projection-expression "#pk" `
        --expression-attribute-names "file://scan-expr.json" `
        --region $Region `
        $(if ($ExclusiveStartKey) { "--exclusive-start-key `"$ExclusiveStartKey`"" }) `
        --output json | ConvertFrom-Json
    
    $ItemsToDelete = @()
    
    foreach ($Item in $Result.Items) {
        $PK = $Item.$KeyName.S
        foreach ($Prefix in $DeletePrefixes) {
            if ($PK.StartsWith($Prefix)) {
                $ItemsToDelete += $PK
                break
            }
        }
    }
    
    # Batch delete
    for ($i = 0; $i -lt $ItemsToDelete.Count; $i += $BatchSize) {
        $Batch = $ItemsToDelete[$i..([Math]::Min($i + $BatchSize - 1, $ItemsToDelete.Count - 1))]
        
        $DeleteRequests = $Batch | ForEach-Object {
            @{
                DeleteRequest = @{
                    Key = @{
                        $KeyName = @{ S = $_ }
                    }
                }
            }
        }
        
        $RequestItems = @{
            $TableName = $DeleteRequests
        }
        
        $Json = $RequestItems | ConvertTo-Json -Depth 10 -Compress
        $Json | Out-File -FilePath "batch-delete.json" -Encoding utf8
        
        aws dynamodb batch-write-item --request-items "file://batch-delete.json" --region $Region | Out-Null
        
        $TotalDeleted += $Batch.Count
        Write-Host "Deleted $TotalDeleted items..." -ForegroundColor Green
    }
    
    $ExclusiveStartKey = $Result.LastEvaluatedKey
    if ($ExclusiveStartKey) {
        $ExclusiveStartKey = ($ExclusiveStartKey | ConvertTo-Json -Compress)
    }
    
} while ($ExclusiveStartKey)

Write-Host "`nTotal deleted: $TotalDeleted items" -ForegroundColor Cyan
Write-Host "Done!" -ForegroundColor Green
