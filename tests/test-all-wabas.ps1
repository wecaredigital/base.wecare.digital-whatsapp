# =============================================================================
# COMPREHENSIVE HANDLER TEST SCRIPT
# =============================================================================
# Tests all handler formats by sending messages to both WABA numbers.
# 
# USAGE:
#   .\tests\test-all-wabas.ps1                    # Run all tests
#   .\tests\test-all-wabas.ps1 -TestCategory core # Run only core tests
#   .\tests\test-all-wabas.ps1 -WabaId 1          # Test only WABA 1
#   .\tests\test-all-wabas.ps1 -DryRun            # Show payloads without invoking
# =============================================================================

param(
    [ValidateSet("all", "core", "extended", "messaging", "media", "query")]
    [string]$TestCategory = "all",
    
    [ValidateSet("all", "1", "2")]
    [string]$WabaId = "all",
    
    [switch]$DryRun,
    [switch]$Verbose
)

# =============================================================================
# CONFIGURATION
# =============================================================================
$REGION = "ap-south-1"
$FUNCTION_NAME = "base-wecare-digital-whatsapp"
$ALIAS_NAME = "live"
$FUNCTION_ARN = "arn:aws:lambda:${REGION}:010526260063:function:${FUNCTION_NAME}:${ALIAS_NAME}"

# WABA Configuration
$WABA_CONFIG = @{
    "1" = @{
        waba_id = "1347766229904230"
        business_name = "WECARE.DIGITAL"
        phone = "+91 93309 94400"
        phone_arn = "arn:aws:social-messaging:ap-south-1:010526260063:phone-number-id/3f8934395ae24a4583a413087a3d3fb0"
        meta_phone_id = "831049713436137"
    }
    "2" = @{
        waba_id = "1390647332755815"
        business_name = "Manish Agarwal"
        phone = "+91 99033 00044"
        phone_arn = "arn:aws:social-messaging:ap-south-1:010526260063:phone-number-id/0b0d77d6d54645d991db7aa9cf1b0eb2"
        meta_phone_id = "888782840987368"
    }
}

# Test recipient (use your own number for testing)
$TEST_RECIPIENT = "919903300044"

# Results tracking
$script:TestResults = @{
    Passed = 0
    Failed = 0
    Skipped = 0
    Details = @()
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
function Write-TestHeader {
    param([string]$Title)
    Write-Host "`n" -NoNewline
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}

function Write-TestResult {
    param(
        [string]$TestName,
        [bool]$Success,
        [string]$Message = "",
        [string]$WabaName = ""
    )
    
    $prefix = if ($WabaName) { "[$WabaName] " } else { "" }
    
    if ($Success) {
        Write-Host "  [PASS] " -ForegroundColor Green -NoNewline
        Write-Host "${prefix}${TestName}" -ForegroundColor White
        $script:TestResults.Passed++
    } else {
        Write-Host "  [FAIL] " -ForegroundColor Red -NoNewline
        Write-Host "${prefix}${TestName}" -ForegroundColor White
        if ($Message) {
            Write-Host "         $Message" -ForegroundColor Yellow
        }
        $script:TestResults.Failed++
    }
    
    $script:TestResults.Details += @{
        Test = $TestName
        Waba = $WabaName
        Success = $Success
        Message = $Message
    }
}

function Invoke-LambdaTest {
    param(
        [string]$TestName,
        [hashtable]$Payload,
        [string]$WabaKey = ""
    )
    
    $wabaName = if ($WabaKey) { $WABA_CONFIG[$WabaKey].business_name } else { "" }
    
    # Add WABA info to payload if specified
    if ($WabaKey -and $WABA_CONFIG.ContainsKey($WabaKey)) {
        $Payload["waba_id"] = $WABA_CONFIG[$WabaKey].waba_id
        $Payload["metaWabaId"] = $WABA_CONFIG[$WabaKey].waba_id
    }
    
    $jsonPayload = $Payload | ConvertTo-Json -Depth 10 -Compress
    
    if ($DryRun) {
        Write-Host "  [DRY] $TestName" -ForegroundColor Yellow
        if ($Verbose) {
            Write-Host "        Payload: $jsonPayload" -ForegroundColor DarkGray
        }
        $script:TestResults.Skipped++
        return $null
    }
    
    try {
        # Write payload to temp file
        $tempFile = [System.IO.Path]::GetTempFileName()
        $responseFile = [System.IO.Path]::GetTempFileName()
        $jsonPayload | Out-File -FilePath $tempFile -Encoding UTF8 -NoNewline
        
        # Invoke Lambda
        $result = aws lambda invoke `
            --region $REGION `
            --function-name $FUNCTION_ARN `
            --payload "fileb://$tempFile" `
            --cli-binary-format raw-in-base64-out `
            $responseFile 2>&1
        
        # Read response
        $response = Get-Content $responseFile -Raw | ConvertFrom-Json
        
        # Cleanup
        Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
        Remove-Item $responseFile -Force -ErrorAction SilentlyContinue
        
        # Check result
        $success = ($response.statusCode -eq 200) -or ($response.statusCode -eq 201)
        $message = if (-not $success) { 
            if ($response.error) { $response.error } 
            elseif ($response.body) { $response.body }
            else { "Status: $($response.statusCode)" }
        } else { "" }
        
        Write-TestResult -TestName $TestName -Success $success -Message $message -WabaName $wabaName
        
        if ($Verbose -and $response) {
            Write-Host "        Response: $($response | ConvertTo-Json -Compress)" -ForegroundColor DarkGray
        }
        
        return $response
    }
    catch {
        Write-TestResult -TestName $TestName -Success $false -Message $_.Exception.Message -WabaName $wabaName
        return $null
    }
}

function Get-WabasToTest {
    if ($WabaId -eq "all") {
        return @("1", "2")
    }
    return @($WabaId)
}

# =============================================================================
# CORE HANDLER TESTS
# =============================================================================
function Test-CoreHandlers {
    Write-TestHeader "CORE HANDLERS"
    
    $wabas = Get-WabasToTest
    
    foreach ($wabaKey in $wabas) {
        Write-Host "`n  Testing WABA: $($WABA_CONFIG[$wabaKey].business_name)" -ForegroundColor Magenta
        
        # 1. Ping
        Invoke-LambdaTest -TestName "ping" -WabaKey $wabaKey -Payload @{
            action = "ping"
        }
        
        # 2. Help
        Invoke-LambdaTest -TestName "help" -WabaKey $wabaKey -Payload @{
            action = "help"
        }
        
        # 3. List Actions
        Invoke-LambdaTest -TestName "list_actions" -WabaKey $wabaKey -Payload @{
            action = "list_actions"
        }
        
        # 4. Get Config
        Invoke-LambdaTest -TestName "get_config" -WabaKey $wabaKey -Payload @{
            action = "get_config"
        }
        
        # 5. Get WABAs
        Invoke-LambdaTest -TestName "get_wabas" -WabaKey $wabaKey -Payload @{
            action = "get_wabas"
        }
        
        # 6. Get Phone Info
        Invoke-LambdaTest -TestName "get_phone_info" -WabaKey $wabaKey -Payload @{
            action = "get_phone_info"
        }
        
        # 7. Get Stats
        Invoke-LambdaTest -TestName "get_stats" -WabaKey $wabaKey -Payload @{
            action = "get_stats"
        }
    }
}

# =============================================================================
# MESSAGING HANDLER TESTS
# =============================================================================
function Test-MessagingHandlers {
    Write-TestHeader "MESSAGING HANDLERS"
    
    $wabas = Get-WabasToTest
    
    foreach ($wabaKey in $wabas) {
        Write-Host "`n  Testing WABA: $($WABA_CONFIG[$wabaKey].business_name)" -ForegroundColor Magenta
        
        # 1. Send Text
        Invoke-LambdaTest -TestName "send_text" -WabaKey $wabaKey -Payload @{
            action = "send_text"
            to = $TEST_RECIPIENT
            text = "Test message from unified handler - WABA $wabaKey - $(Get-Date -Format 'HH:mm:ss')"
        }
        
        # 2. Send Text with Preview URL
        Invoke-LambdaTest -TestName "send_text (preview_url)" -WabaKey $wabaKey -Payload @{
            action = "send_text"
            to = $TEST_RECIPIENT
            text = "Check out https://wecare.digital for more info!"
            preview_url = $true
        }
        
        # 3. Send Reaction (requires valid messageId from previous message)
        Invoke-LambdaTest -TestName "send_reaction" -WabaKey $wabaKey -Payload @{
            action = "send_reaction"
            to = $TEST_RECIPIENT
            messageId = "wamid.test_msg_id"
            emoji = "👍"
        }
        
        # 4. Send Location
        Invoke-LambdaTest -TestName "send_location" -WabaKey $wabaKey -Payload @{
            action = "send_location"
            to = $TEST_RECIPIENT
            latitude = 28.6139
            longitude = 77.2090
            name = "New Delhi"
            address = "India Gate, New Delhi"
        }
        
        # 5. Send Contact
        Invoke-LambdaTest -TestName "send_contact" -WabaKey $wabaKey -Payload @{
            action = "send_contact"
            to = $TEST_RECIPIENT
            contacts = @(
                @{
                    name = @{
                        formatted_name = "Test Contact"
                        first_name = "Test"
                        last_name = "Contact"
                    }
                    phones = @(
                        @{
                            phone = "+919876543210"
                            type = "MOBILE"
                        }
                    )
                }
            )
        }
        
        # 6. Send Interactive (Button)
        Invoke-LambdaTest -TestName "send_interactive (buttons)" -WabaKey $wabaKey -Payload @{
            action = "send_interactive"
            to = $TEST_RECIPIENT
            type = "button"
            body = "Please select an option:"
            buttons = @(
                @{ id = "btn1"; title = "Option 1" }
                @{ id = "btn2"; title = "Option 2" }
            )
        }
        
        # 7. Send Interactive (List)
        Invoke-LambdaTest -TestName "send_interactive (list)" -WabaKey $wabaKey -Payload @{
            action = "send_interactive"
            to = $TEST_RECIPIENT
            type = "list"
            body = "Select from the menu:"
            button = "View Options"
            sections = @(
                @{
                    title = "Section 1"
                    rows = @(
                        @{ id = "row1"; title = "Item 1"; description = "Description 1" }
                        @{ id = "row2"; title = "Item 2"; description = "Description 2" }
                    )
                }
            )
        }
        
        # 8. Send CTA URL
        Invoke-LambdaTest -TestName "send_cta_url" -WabaKey $wabaKey -Payload @{
            action = "send_cta_url"
            to = $TEST_RECIPIENT
            body = "Visit our website for more information"
            buttonText = "Visit Website"
            url = "https://wecare.digital"
        }
        
        # 9. Send Location Request
        Invoke-LambdaTest -TestName "send_location_request" -WabaKey $wabaKey -Payload @{
            action = "send_location_request"
            to = $TEST_RECIPIENT
            body = "Please share your location for delivery"
        }
    }
}

# =============================================================================
# MEDIA HANDLER TESTS
# =============================================================================
function Test-MediaHandlers {
    Write-TestHeader "MEDIA HANDLERS"
    
    $wabas = Get-WabasToTest
    
    foreach ($wabaKey in $wabas) {
        Write-Host "`n  Testing WABA: $($WABA_CONFIG[$wabaKey].business_name)" -ForegroundColor Magenta
        
        # 1. Get Supported Formats
        Invoke-LambdaTest -TestName "get_supported_formats" -WabaKey $wabaKey -Payload @{
            action = "get_supported_formats"
        }
        
        # 2. Get Media Types
        Invoke-LambdaTest -TestName "get_media_types" -WabaKey $wabaKey -Payload @{
            action = "get_media_types"
        }
        
        # 3. Validate Media
        Invoke-LambdaTest -TestName "validate_media" -WabaKey $wabaKey -Payload @{
            action = "validate_media"
            media_type = "image"
            file_size = 1024000
            mime_type = "image/jpeg"
        }
        
        # 4. Send Image (URL)
        Invoke-LambdaTest -TestName "send_image (url)" -WabaKey $wabaKey -Payload @{
            action = "send_image"
            to = $TEST_RECIPIENT
            url = "https://dev.wecare.digital/WhatsApp/test-image.jpg"
            caption = "Test image from WABA $wabaKey"
        }
        
        # 5. Send Document (URL)
        Invoke-LambdaTest -TestName "send_document (url)" -WabaKey $wabaKey -Payload @{
            action = "send_document"
            to = $TEST_RECIPIENT
            url = "https://dev.wecare.digital/WhatsApp/test-doc.pdf"
            filename = "test-document.pdf"
            caption = "Test document"
        }
        
        # 6. EUM Get Supported Formats
        Invoke-LambdaTest -TestName "eum_get_supported_formats" -WabaKey $wabaKey -Payload @{
            action = "eum_get_supported_formats"
        }
        
        # 7. EUM Get Media Stats
        Invoke-LambdaTest -TestName "eum_get_media_stats" -WabaKey $wabaKey -Payload @{
            action = "eum_get_media_stats"
        }
    }
}

# =============================================================================
# QUERY HANDLER TESTS
# =============================================================================
function Test-QueryHandlers {
    Write-TestHeader "QUERY HANDLERS"
    
    $wabas = Get-WabasToTest
    
    foreach ($wabaKey in $wabas) {
        Write-Host "`n  Testing WABA: $($WABA_CONFIG[$wabaKey].business_name)" -ForegroundColor Magenta
        
        # 1. Get Messages
        Invoke-LambdaTest -TestName "get_messages" -WabaKey $wabaKey -Payload @{
            action = "get_messages"
            limit = 5
        }
        
        # 2. Get Conversations
        Invoke-LambdaTest -TestName "get_conversations" -WabaKey $wabaKey -Payload @{
            action = "get_conversations"
            limit = 5
        }
        
        # 3. Get Unread Count
        Invoke-LambdaTest -TestName "get_unread_count" -WabaKey $wabaKey -Payload @{
            action = "get_unread_count"
        }
        
        # 4. Get Quality
        Invoke-LambdaTest -TestName "get_quality" -WabaKey $wabaKey -Payload @{
            action = "get_quality"
        }
        
        # 5. Get Templates
        Invoke-LambdaTest -TestName "get_templates" -WabaKey $wabaKey -Payload @{
            action = "get_templates"
        }
        
        # 6. Search Messages
        Invoke-LambdaTest -TestName "search_messages" -WabaKey $wabaKey -Payload @{
            action = "search_messages"
            query = "test"
            limit = 5
        }
        
        # 7. Get Failed Messages
        Invoke-LambdaTest -TestName "get_failed_messages" -WabaKey $wabaKey -Payload @{
            action = "get_failed_messages"
            limit = 5
        }
    }
}

# =============================================================================
# EXTENDED HANDLER TESTS
# =============================================================================
function Test-ExtendedHandlers {
    Write-TestHeader "EXTENDED HANDLERS"
    
    $wabas = Get-WabasToTest
    
    foreach ($wabaKey in $wabas) {
        Write-Host "`n  Testing WABA: $($WABA_CONFIG[$wabaKey].business_name)" -ForegroundColor Magenta
        
        # Business Profile
        Write-Host "`n    -- Business Profile --" -ForegroundColor DarkCyan
        Invoke-LambdaTest -TestName "get_business_profile" -WabaKey $wabaKey -Payload @{
            action = "get_business_profile"
        }
        
        # Analytics
        Write-Host "`n    -- Analytics --" -ForegroundColor DarkCyan
        Invoke-LambdaTest -TestName "get_analytics" -WabaKey $wabaKey -Payload @{
            action = "get_analytics"
            start_date = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")
            end_date = (Get-Date).ToString("yyyy-MM-dd")
        }
        
        Invoke-LambdaTest -TestName "get_ctwa_metrics" -WabaKey $wabaKey -Payload @{
            action = "get_ctwa_metrics"
        }
        
        Invoke-LambdaTest -TestName "get_funnel_insights" -WabaKey $wabaKey -Payload @{
            action = "get_funnel_insights"
        }
        
        # Webhooks
        Write-Host "`n    -- Webhooks --" -ForegroundColor DarkCyan
        Invoke-LambdaTest -TestName "get_webhook_events" -WabaKey $wabaKey -Payload @{
            action = "get_webhook_events"
            limit = 5
        }
        
        # Calling
        Write-Host "`n    -- Calling --" -ForegroundColor DarkCyan
        Invoke-LambdaTest -TestName "get_call_settings" -WabaKey $wabaKey -Payload @{
            action = "get_call_settings"
        }
        
        Invoke-LambdaTest -TestName "get_call_logs" -WabaKey $wabaKey -Payload @{
            action = "get_call_logs"
            limit = 5
        }
        
        # Groups
        Write-Host "`n    -- Groups --" -ForegroundColor DarkCyan
        Invoke-LambdaTest -TestName "get_groups" -WabaKey $wabaKey -Payload @{
            action = "get_groups"
        }
        
        # Catalogs
        Write-Host "`n    -- Catalogs --" -ForegroundColor DarkCyan
        Invoke-LambdaTest -TestName "get_catalog_products" -WabaKey $wabaKey -Payload @{
            action = "get_catalog_products"
        }
        
        # Payments
        Write-Host "`n    -- Payments --" -ForegroundColor DarkCyan
        Invoke-LambdaTest -TestName "get_payments" -WabaKey $wabaKey -Payload @{
            action = "get_payments"
            limit = 5
        }
        
        Invoke-LambdaTest -TestName "get_payment_status" -WabaKey $wabaKey -Payload @{
            action = "get_payment_status"
            payment_id = "test_payment_123"
        }
        
        # Template Analytics
        Write-Host "`n    -- Template Analytics --" -ForegroundColor DarkCyan
        Invoke-LambdaTest -TestName "get_template_analytics" -WabaKey $wabaKey -Payload @{
            action = "get_template_analytics"
            template_name = "hello_world"
        }
        
        Invoke-LambdaTest -TestName "get_template_pacing" -WabaKey $wabaKey -Payload @{
            action = "get_template_pacing"
        }
    }
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================
Write-Host "`n" -NoNewline
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host " WHATSAPP UNIFIED HANDLER TEST SUITE" -ForegroundColor Green
Write-Host " Lambda: $FUNCTION_NAME" -ForegroundColor Green
Write-Host " Region: $REGION" -ForegroundColor Green
Write-Host " Test Category: $TestCategory" -ForegroundColor Green
Write-Host " WABA Target: $WabaId" -ForegroundColor Green
if ($DryRun) {
    Write-Host " Mode: DRY RUN (no actual invocations)" -ForegroundColor Yellow
}
Write-Host ("=" * 70) -ForegroundColor Green

$startTime = Get-Date

# Run tests based on category
switch ($TestCategory) {
    "all" {
        Test-CoreHandlers
        Test-MessagingHandlers
        Test-MediaHandlers
        Test-QueryHandlers
        Test-ExtendedHandlers
    }
    "core" {
        Test-CoreHandlers
    }
    "messaging" {
        Test-MessagingHandlers
    }
    "media" {
        Test-MediaHandlers
    }
    "query" {
        Test-QueryHandlers
    }
    "extended" {
        Test-ExtendedHandlers
    }
}

$endTime = Get-Date
$duration = $endTime - $startTime

# =============================================================================
# SUMMARY
# =============================================================================
Write-Host "`n" -NoNewline
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host " TEST SUMMARY" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host "  Passed:  $($script:TestResults.Passed)" -ForegroundColor Green
Write-Host "  Failed:  $($script:TestResults.Failed)" -ForegroundColor $(if ($script:TestResults.Failed -gt 0) { "Red" } else { "Green" })
Write-Host "  Skipped: $($script:TestResults.Skipped)" -ForegroundColor Yellow
Write-Host "  Total:   $($script:TestResults.Passed + $script:TestResults.Failed + $script:TestResults.Skipped)" -ForegroundColor White
Write-Host "  Duration: $($duration.TotalSeconds.ToString('F2')) seconds" -ForegroundColor White
Write-Host ("=" * 70) -ForegroundColor Green

# Show failed tests
if ($script:TestResults.Failed -gt 0) {
    Write-Host "`n  Failed Tests:" -ForegroundColor Red
    $script:TestResults.Details | Where-Object { -not $_.Success } | ForEach-Object {
        Write-Host "    - $($_.Test) [$($_.Waba)]: $($_.Message)" -ForegroundColor Red
    }
}

# Exit code
if ($script:TestResults.Failed -gt 0) {
    exit 1
}
exit 0
