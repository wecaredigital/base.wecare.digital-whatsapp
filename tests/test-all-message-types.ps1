# Comprehensive Message Type Test Script
# Tests all message types on both WABAs using UK number (+447447840003)

$API_URL = "https://o0wjog0nl4.execute-api.ap-south-1.amazonaws.com/"
$UK_NUMBER = "+447447840003"

# WABA configurations
$WABAs = @(
    @{Id="1347766229904230"; Name="WECARE.DIGITAL"; Phone="+919330994400"},
    @{Id="1390647332755815"; Name="Manish Agarwal"; Phone="+919903300044"}
)

$results = @()

function Test-Message {
    param($WabaId, $WabaName, $TestName, $Payload)
    
    try {
        $response = Invoke-RestMethod -Uri $API_URL -Method POST -Body ($Payload | ConvertTo-Json -Depth 10) -ContentType "application/json" -ErrorAction Stop
        $status = if ($response.statusCode -eq 200) { "✅ PASS" } else { "❌ FAIL" }
        $msgId = if ($response.messageId) { $response.messageId.Substring(0,8) } else { "N/A" }
        Write-Host "  $status | $TestName | MsgId: $msgId" -ForegroundColor $(if ($response.statusCode -eq 200) { "Green" } else { "Red" })
        return [PSCustomObject]@{WABA=$WabaName;Test=$TestName;Status=$response.statusCode;Result=$status}
    } catch {
        Write-Host "  ❌ FAIL | $TestName | Error: $($_.Exception.Message)" -ForegroundColor Red
        return [PSCustomObject]@{WABA=$WabaName;Test=$TestName;Status="Error";Result="❌ FAIL"}
    }
}

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  COMPREHENSIVE MESSAGE TYPE TEST - ALL WABAs" -ForegroundColor Cyan
Write-Host "  Target: $UK_NUMBER (UK)" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

foreach ($waba in $WABAs) {
    Write-Host "`n========================================" -ForegroundColor Yellow
    Write-Host "WABA: $($waba.Name) ($($waba.Id))" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    
    $wabaId = $waba.Id
    
    # 1. Text Message
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_text" -Payload @{
        action = "send_text"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        text = "Test text message from $($waba.Name)"
    }
    
    # 2. Image Message (URL)
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_image (URL)" -Payload @{
        action = "send_image"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        imageUrl = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Camponotus_flavomarginatus_ant.jpg/320px-Camponotus_flavomarginatus_ant.jpg"
        caption = "Test image from $($waba.Name)"
    }
    
    # 3. Video Message (URL)
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_video (URL)" -Payload @{
        action = "send_video"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        videoUrl = "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4"
        caption = "Test video from $($waba.Name)"
    }
    
    # 4. Document Message (URL)
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_document (URL)" -Payload @{
        action = "send_document"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        documentUrl = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
        filename = "test_document.pdf"
        caption = "Test document from $($waba.Name)"
    }
    
    # 5. Location Message
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_location" -Payload @{
        action = "send_location"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        latitude = 28.6139
        longitude = 77.2090
        name = "New Delhi"
        address = "India Gate, New Delhi, India"
    }
    
    # 6. Contact Message
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_contact" -Payload @{
        action = "send_contact"
        metaWabaId = $wabaId
        to = $UK_NUMBER
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
    
    # 7. Reaction Message
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_reaction" -Payload @{
        action = "send_reaction"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        messageId = "test_message_id"
        emoji = "👍"
    }
    
    # 8. Interactive List Message
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_interactive (list)" -Payload @{
        action = "send_interactive"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        interactiveType = "list"
        headerText = "Choose an Option"
        bodyText = "Please select from the menu below"
        footerText = "Powered by $($waba.Name)"
        buttonText = "View Options"
        sections = @(
            @{
                title = "Products"
                rows = @(
                    @{id = "prod_1"; title = "Product 1"; description = "First product"}
                    @{id = "prod_2"; title = "Product 2"; description = "Second product"}
                )
            }
        )
    }
    
    # 9. Interactive Button Message
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_interactive (buttons)" -Payload @{
        action = "send_interactive"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        interactiveType = "button"
        bodyText = "Would you like to proceed?"
        buttons = @(
            @{id = "yes"; title = "Yes"}
            @{id = "no"; title = "No"}
            @{id = "maybe"; title = "Maybe"}
        )
    }
    
    # 10. CTA URL Button
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_cta_url" -Payload @{
        action = "send_cta_url"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        bodyText = "Visit our website for more information"
        buttonText = "Visit Website"
        url = "https://wecare.digital"
    }
    
    # 11. Sticker Message
    $results += Test-Message -WabaId $wabaId -WabaName $waba.Name -TestName "send_sticker" -Payload @{
        action = "send_sticker"
        metaWabaId = $wabaId
        to = $UK_NUMBER
        stickerUrl = "https://raw.githubusercontent.com/nickymarino/stickers/master/stickers/Pepe/pepe_thumbs_up.webp"
    }
    
    Start-Sleep -Milliseconds 500  # Rate limiting
}

Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host "  TEST RESULTS SUMMARY" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

$results | Format-Table -AutoSize

$passed = ($results | Where-Object { $_.Status -eq 200 }).Count
$total = $results.Count
Write-Host "`nTotal: $passed/$total tests passed" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })
