# =============================================================================
# AWS EUM Social Template Handlers
# =============================================================================
# Template management via AWS End User Messaging Social APIs.
# 
# AWS EUM Template APIs:
# - CreateWhatsAppMessageTemplate
# - UpdateWhatsAppMessageTemplate  
# - DeleteWhatsAppMessageTemplate
# - ListWhatsAppMessageTemplates
# - GetWhatsAppMessageTemplate
# - ListWhatsAppTemplateLibrary
# - CreateWhatsAppMessageTemplateFromLibrary
# - CreateWhatsAppMessageTemplateMedia
#
# Ref: https://docs.aws.amazon.com/social-messaging/latest/APIReference/
# =============================================================================

import json
import logging
from typing import Any, Dict, List, Optional
from handlers.base import (
    table, social, s3, MESSAGES_PK_NAME, MEDIA_BUCKET,
    iso_now, store_item, get_item, validate_required_fields,
    get_waba_config, success_response, error_response
)
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Constants
TEMPLATE_CATEGORIES = ["UTILITY", "MARKETING", "AUTHENTICATION"]
TEMPLATE_STATUSES = ["APPROVED", "PENDING", "REJECTED", "PAUSED", "DISABLED", "IN_APPEAL"]
COMPONENT_TYPES = ["HEADER", "BODY", "FOOTER", "BUTTONS"]
HEADER_FORMATS = ["TEXT", "IMAGE", "VIDEO", "DOCUMENT", "LOCATION"]
BUTTON_TYPES = ["QUICK_REPLY", "URL", "PHONE_NUMBER", "COPY_CODE", "FLOW", "MPM", "CATALOG", "VOICE_CALL"]
LIBRARY_FILTER_KEYS = ["searchKey", "topic", "usecase", "industry", "language"]


def _get_waba_id(meta_waba_id: str) -> str:
    """Get AWS WABA ID from config or use directly if already in AWS format."""
    if not meta_waba_id:
        return ""
    if meta_waba_id.startswith("waba-") or meta_waba_id.startswith("arn:"):
        return meta_waba_id
    config = get_waba_config(meta_waba_id)
    return config.get("wabaId", meta_waba_id)


def _encode_template_definition(template_def: Dict[str, Any]) -> bytes:
    return json.dumps(template_def, ensure_ascii=False).encode("utf-8")


def _encode_template_components(components: List[Dict]) -> bytes:
    return json.dumps(components, ensure_ascii=False).encode("utf-8")


def _decode_template(template_data: Any) -> Dict[str, Any]:
    if isinstance(template_data, bytes):
        return json.loads(template_data.decode("utf-8"))
    elif isinstance(template_data, str):
        return json.loads(template_data)
    return template_data if isinstance(template_data, dict) else {}


def _validate_template_components(components: List[Dict]) -> Dict[str, Any]:
    has_body = False
    for comp in components:
        comp_type = comp.get("type", "")
        if comp_type not in COMPONENT_TYPES:
            return {"valid": False, "error": f"Invalid component type: {comp_type}"}
        if comp_type == "BODY":
            has_body = True
            if not comp.get("text"):
                return {"valid": False, "error": "Body component must have text"}
    if not has_body:
        return {"valid": False, "error": "Template must have a BODY component"}
    return {"valid": True}


def handle_eum_list_templates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """List WhatsApp message templates via AWS EUM API."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    max_results = event.get("maxResults", 50)
    next_token = event.get("nextToken")
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    
    try:
        kwargs = {"id": waba_id}
        if max_results:
            kwargs["maxResults"] = min(max_results, 100)
        if next_token:
            kwargs["nextToken"] = next_token
        
        response = social().list_whatsapp_message_templates(**kwargs)
        templates = response.get("templates", [])
        
        now = iso_now()
        for tpl in templates:
            template_pk = f"TEMPLATE_EUM#{waba_id}#{tpl.get('templateName')}#{tpl.get('templateLanguage', 'en_US')}"
            store_item({
                MESSAGES_PK_NAME: template_pk,
                "itemType": "TEMPLATE_EUM",
                "wabaId": waba_id,
                "templateName": tpl.get("templateName"),
                "metaTemplateId": tpl.get("metaTemplateId"),
                "templateStatus": tpl.get("templateStatus"),
                "templateCategory": tpl.get("templateCategory"),
                "templateLanguage": tpl.get("templateLanguage"),
                "qualityScore": tpl.get("templateQualityScore"),
                "cachedAt": now,
            })
        
        return success_response("eum_list_templates", wabaId=waba_id, count=len(templates),
                                templates=templates, nextToken=response.get("nextToken"))
    except ClientError as e:
        logger.exception(f"EUM list templates failed: {e}")
        return error_response(str(e), 500)


def handle_eum_get_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get a specific WhatsApp message template via AWS EUM API."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    meta_template_id = event.get("metaTemplateId", "")
    
    err = validate_required_fields(event, ["metaTemplateId"])
    if err:
        return err
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    
    try:
        response = social().get_whatsapp_message_template(id=waba_id, metaTemplateId=meta_template_id)
        template_data = _decode_template(response.get("template", "{}"))
        return success_response("eum_get_template", wabaId=waba_id, metaTemplateId=meta_template_id, template=template_data)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            return error_response(f"Template not found: {meta_template_id}", 404)
        logger.exception(f"EUM get template failed: {e}")
        return error_response(str(e), 500)


def handle_eum_create_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a new WhatsApp message template via AWS EUM API."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    name = event.get("name", "")
    language = event.get("language", "en_US")
    category = event.get("category", "UTILITY")
    components = event.get("components", [])
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    err = validate_required_fields(event, ["name", "components"])
    if err:
        return err
    if category not in TEMPLATE_CATEGORIES:
        return error_response(f"Invalid category. Valid: {TEMPLATE_CATEGORIES}")
    
    validation = _validate_template_components(components)
    if not validation.get("valid"):
        return error_response(validation.get("error", "Invalid components"))
    
    template_def = {"name": name, "language": language, "category": category,
                    "components": components, "allow_category_change": event.get("allowCategoryChange", True)}
    template_bytes = _encode_template_definition(template_def)
    
    if len(template_bytes) > 6000:
        return error_response(f"Template definition exceeds 6000 byte limit: {len(template_bytes)} bytes")
    
    try:
        response = social().create_whatsapp_message_template(id=waba_id, templateDefinition=template_bytes)
        meta_template_id = response.get("metaTemplateId", "")
        template_status = response.get("templateStatus", "PENDING")
        
        now = iso_now()
        template_pk = f"TEMPLATE_EUM#{waba_id}#{name}#{language}"
        store_item({
            MESSAGES_PK_NAME: template_pk, "itemType": "TEMPLATE_EUM", "wabaId": waba_id,
            "templateName": name, "metaTemplateId": meta_template_id, "templateStatus": template_status,
            "templateCategory": category, "templateLanguage": language, "components": components,
            "createdAt": now, "createdVia": "AWS_EUM_API",
        })
        
        return success_response("eum_create_template", wabaId=waba_id, templateName=name,
                                metaTemplateId=meta_template_id, templateStatus=template_status,
                                category=category, language=language)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConflictException":
            return error_response(f"Template already exists: {name} ({language})", 409)
        logger.exception(f"EUM create template failed: {e}")
        return error_response(str(e), 500)


def handle_eum_update_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update an existing WhatsApp message template via AWS EUM API."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    meta_template_id = event.get("metaTemplateId", "")
    category = event.get("category")
    components = event.get("components")
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    err = validate_required_fields(event, ["metaTemplateId"])
    if err:
        return err
    if not category and not components:
        return error_response("At least category or components must be provided")
    if category and category not in TEMPLATE_CATEGORIES:
        return error_response(f"Invalid category. Valid: {TEMPLATE_CATEGORIES}")
    if components:
        validation = _validate_template_components(components)
        if not validation.get("valid"):
            return error_response(validation.get("error", "Invalid components"))
    
    try:
        kwargs = {"id": waba_id, "metaTemplateId": meta_template_id}
        if category:
            kwargs["templateCategory"] = category
        if components:
            components_bytes = _encode_template_components(components)
            if len(components_bytes) > 3000:
                return error_response(f"Components exceed 3000 byte limit: {len(components_bytes)} bytes")
            kwargs["templateComponents"] = components_bytes
        
        social().update_whatsapp_message_template(**kwargs)
        return success_response("eum_update_template", wabaId=waba_id, metaTemplateId=meta_template_id, 
                               updated=True, updatedAt=iso_now())
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            return error_response(f"Template not found: {meta_template_id}", 404)
        logger.exception(f"EUM update template failed: {e}")
        return error_response(str(e), 500)


def handle_eum_delete_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete a WhatsApp message template via AWS EUM API."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    template_name = event.get("templateName", "")
    meta_template_id = event.get("metaTemplateId")
    delete_all_languages = event.get("deleteAllLanguages", False)
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    err = validate_required_fields(event, ["templateName"])
    if err:
        return err
    if not meta_template_id and not delete_all_languages:
        return error_response("metaTemplateId is required unless deleteAllLanguages=true")
    
    try:
        kwargs = {"id": waba_id, "templateName": template_name}
        if meta_template_id:
            kwargs["metaTemplateId"] = meta_template_id
        if delete_all_languages:
            kwargs["deleteAllLanguages"] = True
        
        social().delete_whatsapp_message_template(**kwargs)
        
        now = iso_now()
        response = table().scan(
            FilterExpression="itemType = :it AND wabaId = :waba AND templateName = :name",
            ExpressionAttributeValues={":it": "TEMPLATE_EUM", ":waba": waba_id, ":name": template_name},
            Limit=100
        )
        
        deleted_count = 0
        for item in response.get("Items", []):
            if delete_all_languages or item.get("metaTemplateId") == meta_template_id:
                pk = item.get(MESSAGES_PK_NAME)
                table().update_item(
                    Key={MESSAGES_PK_NAME: pk},
                    UpdateExpression="SET templateStatus = :st, deletedAt = :da",
                    ExpressionAttributeValues={":st": "DELETED", ":da": now}
                )
                deleted_count += 1
        
        return success_response("eum_delete_template", wabaId=waba_id, templateName=template_name,
                               metaTemplateId=meta_template_id, deleteAllLanguages=delete_all_languages,
                               localRecordsUpdated=deleted_count)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ResourceNotFoundException":
            return error_response(f"Template not found: {template_name}", 404)
        logger.exception(f"EUM delete template failed: {e}")
        return error_response(str(e), 500)


def handle_eum_list_template_library(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """List templates from Meta's template library via AWS EUM API."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    filters = event.get("filters", {})
    max_results = event.get("maxResults", 50)
    next_token = event.get("nextToken")
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    
    invalid_keys = [k for k in filters.keys() if k not in LIBRARY_FILTER_KEYS]
    if invalid_keys:
        return error_response(f"Invalid filter keys: {invalid_keys}. Valid: {LIBRARY_FILTER_KEYS}")
    
    try:
        kwargs = {"id": waba_id}
        if filters:
            kwargs["filters"] = filters
        if max_results:
            kwargs["maxResults"] = min(max_results, 100)
        if next_token:
            kwargs["nextToken"] = next_token
        
        response = social().list_whatsapp_template_library(**kwargs)
        templates = response.get("metaLibraryTemplates", [])
        
        return success_response("eum_list_template_library", wabaId=waba_id, filters=filters,
                               count=len(templates), templates=templates, nextToken=response.get("nextToken"))
    except ClientError as e:
        logger.exception(f"EUM list template library failed: {e}")
        return error_response(str(e), 500)


def handle_eum_create_from_library(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create a template from Meta's template library via AWS EUM API."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    library_template_id = event.get("libraryTemplateId", "")
    name = event.get("name", "")
    language = event.get("language", "en_US")
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    err = validate_required_fields(event, ["libraryTemplateId", "name"])
    if err:
        return err
    
    try:
        kwargs = {"id": waba_id, "libraryTemplateId": library_template_id,
                  "templateName": name, "templateLanguage": language}
        if event.get("headerVariables"):
            kwargs["headerVariables"] = event["headerVariables"]
        if event.get("bodyVariables"):
            kwargs["bodyVariables"] = event["bodyVariables"]
        if event.get("buttonVariables"):
            kwargs["buttonVariables"] = event["buttonVariables"]
        
        response = social().create_whatsapp_message_template_from_library(**kwargs)
        meta_template_id = response.get("metaTemplateId", "")
        template_status = response.get("templateStatus", "PENDING")
        category = response.get("category", "")
        
        now = iso_now()
        template_pk = f"TEMPLATE_EUM#{waba_id}#{name}#{language}"
        store_item({
            MESSAGES_PK_NAME: template_pk, "itemType": "TEMPLATE_EUM", "wabaId": waba_id,
            "templateName": name, "metaTemplateId": meta_template_id, "templateStatus": template_status,
            "templateCategory": category, "templateLanguage": language, "libraryTemplateId": library_template_id,
            "createdAt": now, "createdVia": "AWS_EUM_LIBRARY",
        })
        
        return success_response("eum_create_from_library", wabaId=waba_id, templateName=name,
                                metaTemplateId=meta_template_id, templateStatus=template_status,
                                category=category, libraryTemplateId=library_template_id)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConflictException":
            return error_response(f"Template already exists: {name} ({language})", 409)
        if error_code == "ResourceNotFoundException":
            return error_response(f"Library template not found: {library_template_id}", 404)
        logger.exception(f"EUM create from library failed: {e}")
        return error_response(str(e), 500)


def handle_eum_create_template_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Upload media for template headers via AWS EUM API."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    s3_key = event.get("s3Key", "")
    s3_bucket = event.get("s3Bucket", str(MEDIA_BUCKET))
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    err = validate_required_fields(event, ["s3Key"])
    if err:
        return err
    
    try:
        head_response = s3().head_object(Bucket=s3_bucket, Key=s3_key)
        content_type = head_response.get("ContentType", "")
        content_length = head_response.get("ContentLength", 0)
        
        valid_types = ["image/jpeg", "image/png", "video/mp4", "application/pdf"]
        if content_type not in valid_types:
            return error_response(f"Invalid media type for template: {content_type}. Valid: {valid_types}")
        
        response = social().create_whatsapp_message_template_media(
            id=waba_id, sourceS3File={"bucketName": s3_bucket, "key": s3_key}
        )
        media_id = response.get("mediaId", "")
        
        now = iso_now()
        store_item({
            MESSAGES_PK_NAME: f"TEMPLATE_MEDIA#{media_id}", "itemType": "TEMPLATE_MEDIA",
            "mediaId": media_id, "wabaId": waba_id, "s3Bucket": s3_bucket, "s3Key": s3_key,
            "contentType": content_type, "contentLength": content_length, "uploadedAt": now,
        })
        
        return success_response("eum_create_template_media", wabaId=waba_id, mediaId=media_id,
                                s3Key=s3_key, contentType=content_type)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "NoSuchKey":
            return error_response(f"S3 object not found: {s3_key}", 404)
        logger.exception(f"EUM create template media failed: {e}")
        return error_response(str(e), 500)


def handle_eum_sync_templates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Sync all templates from AWS EUM to local cache."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    
    try:
        all_templates = []
        next_token = None
        
        while True:
            kwargs = {"id": waba_id, "maxResults": 100}
            if next_token:
                kwargs["nextToken"] = next_token
            response = social().list_whatsapp_message_templates(**kwargs)
            all_templates.extend(response.get("templates", []))
            next_token = response.get("nextToken")
            if not next_token:
                break
        
        now = iso_now()
        for tpl in all_templates:
            template_pk = f"TEMPLATE_EUM#{waba_id}#{tpl.get('templateName')}#{tpl.get('templateLanguage', 'en_US')}"
            store_item({
                MESSAGES_PK_NAME: template_pk, "itemType": "TEMPLATE_EUM", "wabaId": waba_id,
                "templateName": tpl.get("templateName"), "metaTemplateId": tpl.get("metaTemplateId"),
                "templateStatus": tpl.get("templateStatus"), "templateCategory": tpl.get("templateCategory"),
                "templateLanguage": tpl.get("templateLanguage"), "qualityScore": tpl.get("templateQualityScore"),
                "syncedAt": now,
            })
        
        return success_response("eum_sync_templates", wabaId=waba_id, syncedCount=len(all_templates), syncedAt=now)
    except ClientError as e:
        logger.exception(f"EUM sync templates failed: {e}")
        return error_response(str(e), 500)


def handle_eum_get_template_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get template status from local cache."""
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    template_name = event.get("templateName", "")
    language = event.get("language", "en_US")
    
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    err = validate_required_fields(event, ["templateName"])
    if err:
        return err
    
    template_pk = f"TEMPLATE_EUM#{waba_id}#{template_name}#{language}"
    
    try:
        item = get_item(template_pk)
        if not item:
            return error_response(f"Template not found in cache: {template_name} ({language})", 404)
        
        return success_response("eum_get_template_status", wabaId=waba_id, templateName=template_name,
                                language=language, metaTemplateId=item.get("metaTemplateId"),
                                status=item.get("templateStatus"), category=item.get("templateCategory"),
                                qualityScore=item.get("qualityScore"),
                                cachedAt=item.get("cachedAt") or item.get("syncedAt"))
    except ClientError as e:
        logger.exception(f"Get template status failed: {e}")
        return error_response(str(e), 500)


# =============================================================================
# HANDLER MAPPING
# =============================================================================
EUM_TEMPLATE_HANDLERS = {
    "eum_list_templates": handle_eum_list_templates,
    "eum_get_template": handle_eum_get_template,
    "eum_create_template": handle_eum_create_template,
    "eum_update_template": handle_eum_update_template,
    "eum_delete_template": handle_eum_delete_template,
    "eum_list_template_library": handle_eum_list_template_library,
    "eum_create_from_library": handle_eum_create_from_library,
    "eum_create_template_media": handle_eum_create_template_media,
    "eum_sync_templates": handle_eum_sync_templates,
    "eum_get_template_status": handle_eum_get_template_status,
}
