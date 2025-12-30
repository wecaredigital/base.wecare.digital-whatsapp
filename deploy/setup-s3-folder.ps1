# S3 Folder Setup Script
# Creates the WhatsApp folder structure in S3

$REGION = "ap-south-1"
$BUCKET = "dev.wecare.digital"
$PREFIX = "base-wecare-digital/"

Write-Host "=== Creating S3 folder structure ===" -ForegroundColor Green

# Create a placeholder file to establish the folder structure
$PLACEHOLDER_CONTENT = "# WhatsApp Media Storage`nThis folder contains WhatsApp media files downloaded from inbound messages."

# Create temp file
$TEMP_FILE = [System.IO.Path]::GetTempFileName()
Set-Content -Path $TEMP_FILE -Value $PLACEHOLDER_CONTENT

# Upload to establish folder
aws s3 cp $TEMP_FILE "s3://${BUCKET}/${PREFIX}WhatsApp/.folder-info.txt" --region $REGION

# Cleanup
Remove-Item $TEMP_FILE -Force

Write-Host "Created folder: s3://${BUCKET}/${PREFIX}WhatsApp/"
Write-Host "`nMedia will be stored at:"
Write-Host "s3://${BUCKET}/WhatsApp/business=<name>/wabaMetaId=<id>/phone=<phone-id>/from=<wa_id>/waMessageId=<wamid>/mediaId=<id>.<ext>"
