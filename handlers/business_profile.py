# =============================================================================
# Business Profile Handlers (AWS EUM Social - CRM Local Pattern)
# =============================================================================
# Business Profile management with CRM-local metadata storage.
# 
# AWS EUM Constraint:
# - AWS End User Messaging Social does NOT currently expose Business Profile
#   update APIs. Profile updates must be done via Meta Business Manager console.
# 
# Implementation Pattern:
# - Store profile metadata locally in DynamoDB (per tenant + phoneNumberId)
# - Provide get/update operations for CRM-local data
# - Provide "Apply to WhatsApp" runbook action with console steps
# - Design for upgrade: capability flag + provider stub for future AWS API
#
# Ref: https://developers.facebook.com/docs/whatsapp/business-management-api/business-profiles
# =============================================================================

import json
import logging
from typing import Any, Dict, Optional
from enum import Enum
from handlers.base import (
    table, social, s3, MESSAGES_PK_NAME, MEDIA_BUCKET, MEDIA_PREFIX,
    iso_now, get_phone_arn, get_waba_config, validate_required_fields,
    store_item, get_item, origination_id_for_api, META_API_VERSION,
    success_response, error_response
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# =============================================================================
# CAPABILITY FLAGS (Upgrade Hooks)
# =============================================================================
class Capability(Enum):
    """Feature capability flags for upgrade-friendly design."""
    # Business Profile remote update via AWS EUM API
    # Set to True when AWS adds this capability
    BUSINESS_PROFILE_REMOTE_UPDATE = False
    
    # Business Profile avatar upload via AWS EUM API
    BUSINESS_PROFILE_AVATAR_UPLOAD = True  # Supported via post_whatsapp_message_media


def is_capability_enabled(capability: Capability) -> bool:
    """Check if a capability is enabled."""
    return capability.value


# =============================================================================
# AWS EUM PROVIDER STUBS (Upgrade Hooks)
# =============================================================================
class AwsEumProvider:
    """
    AWS EUM Social provider with stubs for future capabilities.
    
    When AWS adds new APIs, implement them here without refactoring handlers.
    """
    
    @staticmethod
    def update_business_profile(phone_arn: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update business profile via AWS EUM API.
        
        STUB: Not currently supported by AWS EUM Social.
        When AWS adds this capability:
        1. Set Capability.BUSINESS_PROFILE_REMOTE_UPDATE = True
        2. Implement the actual API call here
        
        Returns:
            Dict with success=False and NotSupported error
        """
        if not is_capability_enabled(Capability.BUSINESS_PROFILE_REMOTE_UPDATE):
            return {
                "success": False,
                "error": "NotSupported",
                "message": "Business Profile update is not supported via AWS EUM API. Use Meta Business Manager console.",
                "upgradeHint": "This capability will be implemented when AWS adds the API."
            }
        
        # Future implementation:
        # response = social().update_whatsapp_business_profile(
        #     originationPhoneNumberId=origination_id_for_api(phone_arn),
        #     profileData=profile_data
        # )
        # return {"success": True, "response": response}
        
        return {"success": False, "error": "NotImplemented"}
    
    @staticmethod
    def get_business_profile(phone_arn: str) -> Dict[str, Any]:
        """
        Get business profile via AWS EUM API.
        
        STUB: Not currently supported by AWS EUM Social.
        """
        if not is_capability_enabled(Capability.BUSINESS_PROFILE_REMOTE_UPDATE):
            return {
                "success": False,
                "error": "NotSupported",
                "message": "Business Profile fetch is not supported via AWS EUM API."
            }
        
        return {"success": False, "error": "NotImplemented"}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def _build_profile_pk(tenant_id: str, phone_number_id: str) -> str:
    """Build DynamoDB PK for business profile."""
    return f"PROFILE#{tenant_id}#{phone_number_id}"


def _build_profile_pk_by_waba(meta_waba_id: str) -> str:
    """Build DynamoDB PK for business profile by WABA ID."""
    return f"PROFILE#{meta_waba_id}"


# =============================================================================
# GET BUSINESS PROFILE
# =============================================================================
def handle_get_business_profile(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get business profile details from CRM-local storage.
    
    Returns profile metadata stored in DynamoDB. If not found, creates
    a default profile from WABA configuration.
    
    Test Event:
    {
        "action": "get_business_profile",
        "metaWabaId": "1347766229904230"
    }
    
    Or with tenant ID:
    {
        "action": "get_business_profile",
        "tenantId": "wecare-digital",
        "phoneNumberId": "phone-number-id-xxx"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    tenant_id = event.get("tenantId", "")
    phone_number_id = event.get("phoneNumberId", "")
    
    # Determine profile PK
    if tenant_id and phone_number_id:
        profile_pk = _build_profile_pk(tenant_id, phone_number_id)
    elif meta_waba_id:
        profile_pk = _build_profile_pk_by_waba(meta_waba_id)
    else:
        return error_response("metaWabaId or (tenantId + phoneNumberId) is required", 400)
    
    phone_arn = ""
    if meta_waba_id:
        phone_arn = get_phone_arn(meta_waba_id)
        if not phone_arn:
            return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    # Check cache first
    try:
        cached = get_item(profile_pk)
        if cached:
            return success_response(
                "get_business_profile",
                profile=cached,
                cached=True,
                remoteUpdateSupported=is_capability_enabled(Capability.BUSINESS_PROFILE_REMOTE_UPDATE)
            )
    except ClientError:
        pass
    
    # Create default profile from WABA config
    try:
        waba_config = get_waba_config(meta_waba_id) if meta_waba_id else {}
        
        profile_data = {
            MESSAGES_PK_NAME: profile_pk,
            "itemType": "BUSINESS_PROFILE",
            "wabaMetaId": meta_waba_id,
            "tenantId": tenant_id or meta_waba_id,
            "phoneNumberId": phone_number_id,
            "businessName": waba_config.get("businessAccountName", ""),
            "phone": waba_config.get("phone", ""),
            "phoneArn": phone_arn,
            "createdAt": iso_now(),
            "lastUpdatedAt": iso_now(),
            # Profile fields (CRM-local)
            "about": "",
            "address": "",
            "description": "",
            "email": "",
            "profilePictureUrl": "",
            "websites": [],
            "vertical": "",
            # Sync status
            "syncStatus": "local_only",
            "lastSyncedToWhatsApp": None,
        }
        
        store_item(profile_data)
        
        return success_response(
            "get_business_profile",
            profile=profile_data,
            cached=False,
            remoteUpdateSupported=is_capability_enabled(Capability.BUSINESS_PROFILE_REMOTE_UPDATE)
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# UPDATE BUSINESS PROFILE (CRM-Local)
# =============================================================================
def handle_update_business_profile(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update business profile in CRM-local storage.
    
    Updates profile metadata in DynamoDB. Does NOT sync to WhatsApp automatically.
    Use get_business_profile_apply_instructions for manual sync steps.
    
    Test Event:
    {
        "action": "update_business_profile",
        "metaWabaId": "1347766229904230",
        "data": {
            "about": "My Business sells products",
            "address": "123 Business St",
            "description": "We sell quality products",
            "email": "contact@business.com",
            "websites": ["https://www.business.com"],
            "vertical": "RETAIL"
        }
    }
    
    With profile picture from S3:
    {
        "action": "update_business_profile",
        "metaWabaId": "1347766229904230",
        "profilePictureS3Key": "WhatsApp/profiles/avatar.jpg",
        "data": {
            "about": "Updated business description"
        }
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    tenant_id = event.get("tenantId", "")
    phone_number_id = event.get("phoneNumberId", "")
    data = event.get("data", {})
    profile_picture_s3_key = event.get("profilePictureS3Key", "")
    try_remote_update = event.get("tryRemoteUpdate", False)
    
    # Determine profile PK
    if tenant_id and phone_number_id:
        profile_pk = _build_profile_pk(tenant_id, phone_number_id)
    elif meta_waba_id:
        profile_pk = _build_profile_pk_by_waba(meta_waba_id)
    else:
        return error_response("metaWabaId or (tenantId + phoneNumberId) is required", 400)
    
    phone_arn = ""
    if meta_waba_id:
        phone_arn = get_phone_arn(meta_waba_id)
        if not phone_arn:
            return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    now = iso_now()
    
    try:
        # Handle profile picture upload to WhatsApp
        profile_picture_handle = ""
        if profile_picture_s3_key and phone_arn:
            upload_resp = social().post_whatsapp_message_media(
                originationPhoneNumberId=origination_id_for_api(phone_arn),
                sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": profile_picture_s3_key},
            )
            profile_picture_handle = upload_resp.get("mediaId", "")
        
        # Build update expression
        update_parts = ["lastUpdatedAt = :now"]
        expr_values = {":now": now}
        expr_names = {}
        
        # Add profile fields
        profile_fields = ["about", "address", "description", "email", "websites", "vertical"]
        for field in profile_fields:
            if field in data:
                update_parts.append(f"#{field} = :{field}")
                expr_names[f"#{field}"] = field
                expr_values[f":{field}"] = data[field]
        
        if profile_picture_handle:
            update_parts.append("profilePictureHandle = :pph")
            update_parts.append("profilePictureS3Key = :pps")
            expr_values[":pph"] = profile_picture_handle
            expr_values[":pps"] = profile_picture_s3_key
        
        # Mark as pending sync
        update_parts.append("syncStatus = :ss")
        expr_values[":ss"] = "pending_sync"
        
        # Update DynamoDB
        table().update_item(
            Key={MESSAGES_PK_NAME: profile_pk},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names if expr_names else None
        )
        
        # Try remote update if requested and supported
        remote_result = None
        if try_remote_update:
            remote_result = AwsEumProvider.update_business_profile(phone_arn, data)
            if remote_result.get("success"):
                # Update sync status
                table().update_item(
                    Key={MESSAGES_PK_NAME: profile_pk},
                    UpdateExpression="SET syncStatus = :ss, lastSyncedToWhatsApp = :lst",
                    ExpressionAttributeValues={":ss": "synced", ":lst": now}
                )
        
        return success_response(
            "update_business_profile",
            updated=True,
            profilePk=profile_pk,
            updatedFields=list(data.keys()),
            profilePictureUploaded=bool(profile_picture_handle),
            remoteUpdateResult=remote_result,
            syncStatus="pending_sync" if not (remote_result and remote_result.get("success")) else "synced",
            applyInstructions="Use action='get_business_profile_apply_instructions' for manual sync steps"
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# UPLOAD PROFILE AVATAR
# =============================================================================
def handle_upload_profile_picture(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Upload profile picture to S3 and WhatsApp.
    
    Test Event:
    {
        "action": "upload_profile_picture",
        "metaWabaId": "1347766229904230",
        "s3Key": "WhatsApp/profiles/avatar.jpg"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    s3_key = event.get("s3Key", "")
    
    err = validate_required_fields(event, ["metaWabaId", "s3Key"])
    if err:
        return err
    
    phone_arn = get_phone_arn(meta_waba_id)
    if not phone_arn:
        return error_response(f"Phone not found for WABA: {meta_waba_id}", 404)
    
    try:
        # Upload to WhatsApp
        upload_resp = social().post_whatsapp_message_media(
            originationPhoneNumberId=origination_id_for_api(phone_arn),
            sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key},
        )
        media_id = upload_resp.get("mediaId", "")
        
        # Store reference
        now = iso_now()
        store_item({
            MESSAGES_PK_NAME: f"PROFILE_PIC#{meta_waba_id}#{now}",
            "itemType": "PROFILE_PICTURE",
            "wabaMetaId": meta_waba_id,
            "s3Key": s3_key,
            "mediaId": media_id,
            "uploadedAt": now,
        })
        
        return success_response(
            "upload_profile_picture",
            mediaId=media_id,
            s3Key=s3_key
        )
    except ClientError as e:
        return error_response(str(e), 500)


# =============================================================================
# GET APPLY INSTRUCTIONS (Runbook Action)
# =============================================================================
def handle_get_business_profile_apply_instructions(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get instructions for applying business profile changes to WhatsApp.
    
    Since AWS EUM does not support remote profile updates, this provides
    step-by-step instructions for manual sync via Meta Business Manager.
    
    Test Event:
    {
        "action": "get_business_profile_apply_instructions",
        "metaWabaId": "1347766229904230"
    }
    """
    meta_waba_id = event.get("metaWabaId", "")
    
    err = validate_required_fields(event, ["metaWabaId"])
    if err:
        return err
    
    # Get current profile data
    profile_pk = _build_profile_pk_by_waba(meta_waba_id)
    profile = get_item(profile_pk)
    
    if not profile:
        return error_response(f"Profile not found for WABA: {meta_waba_id}", 404)
    
    # Build instructions
    instructions = {
        "title": "Apply Business Profile to WhatsApp",
        "description": "Follow these steps to update your WhatsApp Business Profile in Meta Business Manager",
        "remoteUpdateSupported": is_capability_enabled(Capability.BUSINESS_PROFILE_REMOTE_UPDATE),
        "steps": [
            {
                "step": 1,
                "action": "Open Meta Business Manager",
                "url": "https://business.facebook.com/",
                "details": "Log in with your business account credentials"
            },
            {
                "step": 2,
                "action": "Navigate to WhatsApp Manager",
                "details": "Go to All Tools > WhatsApp Manager"
            },
            {
                "step": 3,
                "action": "Select your WhatsApp Business Account",
                "details": f"Select the account with WABA ID: {meta_waba_id}"
            },
            {
                "step": 4,
                "action": "Go to Phone Numbers",
                "details": "Click on 'Phone numbers' in the left sidebar"
            },
            {
                "step": 5,
                "action": "Edit Business Profile",
                "details": "Click on your phone number, then 'Edit' next to Business Profile"
            },
            {
                "step": 6,
                "action": "Update Profile Fields",
                "details": "Update the following fields with your CRM data:",
                "fields": {
                    "About": profile.get("about", ""),
                    "Address": profile.get("address", ""),
                    "Description": profile.get("description", ""),
                    "Email": profile.get("email", ""),
                    "Websites": profile.get("websites", []),
                    "Category": profile.get("vertical", "")
                }
            },
            {
                "step": 7,
                "action": "Upload Profile Picture (if changed)",
                "details": f"Upload the image from S3: {profile.get('profilePictureS3Key', 'N/A')}"
            },
            {
                "step": 8,
                "action": "Save Changes",
                "details": "Click 'Save' to apply the changes"
            }
        ],
        "currentProfile": profile,
        "syncStatus": profile.get("syncStatus", "unknown"),
        "lastSyncedToWhatsApp": profile.get("lastSyncedToWhatsApp"),
        "upgradeNote": "When AWS EUM adds Business Profile update API, this action will sync automatically."
    }
    
    return success_response(
        "get_business_profile_apply_instructions",
        instructions=instructions
    )
