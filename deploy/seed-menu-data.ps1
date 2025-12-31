# =============================================================================
# Seed Welcome + Menu Data in DynamoDB
# =============================================================================
$REGION = "ap-south-1"
$TABLE = "base-wecare-digital-whatsapp"
$TENANT_ID = "1347766229904230"

Write-Host "Seeding Welcome + Menu data for tenant: $TENANT_ID" -ForegroundColor Cyan

# Welcome Config
$welcomeItem = @"
{
    "pk": {"S": "TENANT#$TENANT_ID"},
    "sk": {"S": "WELCOME#default"},
    "itemType": {"S": "WELCOME_CONFIG"},
    "welcomeText": {"S": "Welcome to WECARE.DIGITAL 👋 Choose an option from the menu below, or type what you need help with."},
    "enabled": {"BOOL": true},
    "onlyOnFirstContact": {"BOOL": false},
    "cooldownHours": {"N": "72"},
    "createdAt": {"S": "$(Get-Date -Format 'o')"}
}
"@
aws dynamodb put-item --table-name $TABLE --item $welcomeItem --region $REGION
Write-Host "  + Welcome config" -ForegroundColor Green

# Main Menu
$mainMenu = @"
{
    "pk": {"S": "TENANT#$TENANT_ID"},
    "sk": {"S": "MENU#main"},
    "itemType": {"S": "MENU_CONFIG"},
    "buttonText": {"S": "Menu"},
    "bodyText": {"S": "Pick a category. You'll get a short answer + link."},
    "sections": {"L": [
        {"M": {
            "title": {"S": "START HERE"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "go_services"}, "title": {"S": "Services & Brands"}, "description": {"S": "Explore WECARE brands"}, "actionType": {"S": "open_submenu"}, "actionValue": {"S": "services"}, "answerText": {"S": "Here are our services & brands. Pick one to learn more."}}},
                {"M": {"rowId": {"S": "go_self_service"}, "title": {"S": "Self Service"}, "description": {"S": "Forms, docs, tracking"}, "actionType": {"S": "open_submenu"}, "actionValue": {"S": "self_service"}, "answerText": {"S": "Here are quick self-service options."}}},
                {"M": {"rowId": {"S": "go_support"}, "title": {"S": "Support & Contact"}, "description": {"S": "Payments, FAQ, contact"}, "actionType": {"S": "open_submenu"}, "actionValue": {"S": "support"}, "answerText": {"S": "Here are support and contact options."}}}
            ]}
        }},
        {"M": {
            "title": {"S": "QUICK ACTIONS"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "quick_submit"}, "title": {"S": "Submit Request"}, "description": {"S": "Start a new request"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/submit-request"}, "answerText": {"S": "To start a new request, use this short form:"}}},
                {"M": {"rowId": {"S": "quick_track"}, "title": {"S": "Track Request"}, "description": {"S": "Check status"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/request-tracking"}, "answerText": {"S": "You can track your request status here:"}}}
            ]}
        }}
    ]},
    "createdAt": {"S": "$(Get-Date -Format 'o')"}
}
"@
$mainMenu | Out-File -FilePath "temp-main-menu.json" -Encoding UTF8
aws dynamodb put-item --table-name $TABLE --cli-input-json "file://temp-main-menu.json" --region $REGION 2>$null
if ($LASTEXITCODE -ne 0) {
    # Fallback: use inline
    aws dynamodb put-item --table-name $TABLE --item $mainMenu --region $REGION
}
Write-Host "  + Main menu" -ForegroundColor Green

# Services Submenu
$servicesMenu = @"
{
    "pk": {"S": "TENANT#$TENANT_ID"},
    "sk": {"S": "MENU#services"},
    "itemType": {"S": "MENU_CONFIG"},
    "buttonText": {"S": "Services"},
    "bodyText": {"S": "Select a brand. I'll share a 1-line summary + link."},
    "sections": {"L": [
        {"M": {
            "title": {"S": "MICRO-SERVICE BRANDS"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "svc_bnb"}, "title": {"S": "BNB CLUB"}, "description": {"S": "Travel & stays"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/bnb-club"}, "answerText": {"S": "BNB CLUB: a WECARE.DIGITAL travel offering. Details:"}}},
                {"M": {"rowId": {"S": "svc_nofault"}, "title": {"S": "NO FAULT"}, "description": {"S": "ODR & resolution"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/no-fault"}, "answerText": {"S": "NO FAULT: an online-resolution (ODR) service line. Details:"}}},
                {"M": {"rowId": {"S": "svc_expo"}, "title": {"S": "EXPO WEEK"}, "description": {"S": "Digital events"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/expo-week"}, "answerText": {"S": "EXPO WEEK: our events & showcases. Details:"}}},
                {"M": {"rowId": {"S": "svc_ritual"}, "title": {"S": "RITUAL GURU"}, "description": {"S": "Culture & rituals"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/ritual-guru"}, "answerText": {"S": "RITUAL GURU: culture-focused guidance. Details:"}}},
                {"M": {"rowId": {"S": "svc_legal"}, "title": {"S": "LEGAL CHAMP"}, "description": {"S": "Documentation help"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/legal-champ"}, "answerText": {"S": "LEGAL CHAMP: documentation and support. Details:"}}},
                {"M": {"rowId": {"S": "svc_swdhya"}, "title": {"S": "SWDHYA"}, "description": {"S": "Samvad & learning"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/swdhya"}, "answerText": {"S": "SWDHYA: learning & samvad. Details:"}}}
            ]}
        }}
    ]},
    "createdAt": {"S": "$(Get-Date -Format 'o')"}
}
"@
aws dynamodb put-item --table-name $TABLE --item $servicesMenu --region $REGION
Write-Host "  + Services submenu" -ForegroundColor Green

# Self Service Submenu
$selfServiceMenu = @"
{
    "pk": {"S": "TENANT#$TENANT_ID"},
    "sk": {"S": "MENU#self_service"},
    "itemType": {"S": "MENU_CONFIG"},
    "buttonText": {"S": "Self Service"},
    "bodyText": {"S": "Choose an action. I'll explain in 1 line + share the link."},
    "sections": {"L": [
        {"M": {
            "title": {"S": "FORMS & REQUESTS"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "ss_submit"}, "title": {"S": "Submit Request"}, "description": {"S": "New request"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/submit-request"}, "answerText": {"S": "Submit a new request here:"}}},
                {"M": {"rowId": {"S": "ss_amend"}, "title": {"S": "Request Amendment"}, "description": {"S": "Update a request"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/request-amendment"}, "answerText": {"S": "Need to change something? Use this amendment form:"}}},
                {"M": {"rowId": {"S": "ss_track"}, "title": {"S": "Request Tracking"}, "description": {"S": "Status check"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/request-tracking"}, "answerText": {"S": "Track your request here:"}}}
            ]}
        }},
        {"M": {
            "title": {"S": "DOCUMENTS"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "ss_dropdocs"}, "title": {"S": "Drop Docs"}, "description": {"S": "Upload documents"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/drop-docs"}, "answerText": {"S": "Upload or drop documents here:"}}}
            ]}
        }},
        {"M": {
            "title": {"S": "ENTERPRISE"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "ss_enterprise"}, "title": {"S": "Enterprise Assist"}, "description": {"S": "Business support"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/enterprise-assist"}, "answerText": {"S": "For enterprise support, start here:"}}}
            ]}
        }}
    ]},
    "createdAt": {"S": "$(Get-Date -Format 'o')"}
}
"@
aws dynamodb put-item --table-name $TABLE --item $selfServiceMenu --region $REGION
Write-Host "  + Self Service submenu" -ForegroundColor Green

# Support Submenu
$supportMenu = @"
{
    "pk": {"S": "TENANT#$TENANT_ID"},
    "sk": {"S": "MENU#support"},
    "itemType": {"S": "MENU_CONFIG"},
    "buttonText": {"S": "Support"},
    "bodyText": {"S": "Support options. I'll share a short answer + link."},
    "sections": {"L": [
        {"M": {
            "title": {"S": "HELP"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "sup_faq"}, "title": {"S": "FAQ"}, "description": {"S": "Common questions"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/faq"}, "answerText": {"S": "Here are the FAQs:"}}},
                {"M": {"rowId": {"S": "sup_contact"}, "title": {"S": "Contact Us"}, "description": {"S": "Talk to WECARE"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/contact"}, "answerText": {"S": "You can contact WECARE here:"}}},
                {"M": {"rowId": {"S": "sup_review"}, "title": {"S": "Leave Review"}, "description": {"S": "Share feedback"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/leave-review"}, "answerText": {"S": "We'd love feedback—use this link:"}}}
            ]}
        }},
        {"M": {
            "title": {"S": "APPS & CAREERS"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "sup_app"}, "title": {"S": "Download App"}, "description": {"S": "Get the app"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/app"}, "answerText": {"S": "Download the WECARE app here:"}}},
                {"M": {"rowId": {"S": "sup_careers"}, "title": {"S": "Careers"}, "description": {"S": "Work with us"}, "actionType": {"S": "open_url"}, "actionValue": {"S": "https://www.wecare.digital/careers"}, "answerText": {"S": "Explore careers here:"}}}
            ]}
        }},
        {"M": {
            "title": {"S": "PAYMENTS"},
            "rows": {"L": [
                {"M": {"rowId": {"S": "sup_pay_help"}, "title": {"S": "Payments Help"}, "description": {"S": "UPI / gateway info"}, "actionType": {"S": "invoke_action"}, "actionValue": {"S": "get_payment_help"}, "answerText": {"S": "Tell me which business number you're paying (WECARE-DIGITAL or ManishAgarwal) and I'll share the right payment steps."}}}
            ]}
        }}
    ]},
    "createdAt": {"S": "$(Get-Date -Format 'o')"}
}
"@
aws dynamodb put-item --table-name $TABLE --item $supportMenu --region $REGION
Write-Host "  + Support submenu" -ForegroundColor Green

# Cleanup
Remove-Item temp-*.json -ErrorAction SilentlyContinue

Write-Host "`nMenu data seeded successfully!" -ForegroundColor Green
