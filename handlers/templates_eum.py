# =============================================================================
# AWS EUM Social Template Handlers
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

TEMPLATE_CATEGORIES = ["UTILITY", "MARKETING", "AUTHENTICATION"]
COMPONENT_TYPES = ["HEADER", "BODY", "FOOTER", "BUTTONS"]
LIBRARY_FILTER_KEYS = ["searchKey", "topic", "usecase", "industry", "language"]

def _get_waba_id(meta_waba_id: str) -> str:
    if not meta_waba_id:
        return ""
    if meta_waba_id.startswith("waba-") or meta_waba_id.startswith("arn:"):
        return meta_waba_id
    config = get_waba_config(meta_waba_id)
    return config.get("wabaId", meta_waba_id)

def _encode_template_definition(template_def: Dict[str, Any]) -> bytes:
    return json.dumps(template_def, ensure_ascii=False).encode("utf-8")

def _validate_template_components(components: List[Dict]) -> Dict[str, Any]:
    has_body = any(c.get("type") == "BODY" for c in components)
    if not has_body:
        return {"valid": False, "error": "Template must have a BODY component"}
    return {"valid": True}

def handle_eum_list_templates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    try:
        response = social().list_whatsapp_message_templates(id=waba_id, maxResults=event.get("maxResults", 50))
        return success_response("eum_list_templates", wabaId=waba_id, templates=response.get("templates", []))
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_get_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    meta_template_id = event.get("metaTemplateId", "")
    if not waba_id or not meta_template_id:
        return error_response("wabaId and metaTemplateId are required")
    try:
        response = social().get_whatsapp_message_template(id=waba_id, metaTemplateId=meta_template_id)
        return success_response("eum_get_template", wabaId=waba_id, template=response.get("template"))
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_create_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    name = event.get("name", "")
    components = event.get("components", [])
    if not waba_id or not name or not components:
        return error_response("wabaId, name, and components are required")
    template_def = {"name": name, "language": event.get("language", "en_US"), 
                    "category": event.get("category", "UTILITY"), "components": components}
    try:
        response = social().create_whatsapp_message_template(id=waba_id, templateDefinition=_encode_template_definition(template_def))
        return success_response("eum_create_template", wabaId=waba_id, metaTemplateId=response.get("metaTemplateId"))
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_update_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    meta_template_id = event.get("metaTemplateId", "")
    if not waba_id or not meta_template_id:
        return error_response("wabaId and metaTemplateId are required")
    try:
        social().update_whatsapp_message_template(id=waba_id, metaTemplateId=meta_template_id)
        return success_response("eum_update_template", wabaId=waba_id, updated=True)
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_delete_template(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    template_name = event.get("templateName", "")
    if not waba_id or not template_name:
        return error_response("wabaId and templateName are required")
    try:
        social().delete_whatsapp_message_template(id=waba_id, templateName=template_name)
        return success_response("eum_delete_template", wabaId=waba_id, deleted=True)
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_list_template_library(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    try:
        response = social().list_whatsapp_template_library(id=waba_id)
        return success_response("eum_list_template_library", wabaId=waba_id, templates=response.get("metaLibraryTemplates", []))
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_create_from_library(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    library_template_id = event.get("libraryTemplateId", "")
    name = event.get("name", "")
    if not waba_id or not library_template_id or not name:
        return error_response("wabaId, libraryTemplateId, and name are required")
    try:
        response = social().create_whatsapp_message_template_from_library(
            id=waba_id, libraryTemplateId=library_template_id, templateName=name, templateLanguage=event.get("language", "en_US"))
        return success_response("eum_create_from_library", wabaId=waba_id, metaTemplateId=response.get("metaTemplateId"))
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_create_template_media(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    s3_key = event.get("s3Key", "")
    if not waba_id or not s3_key:
        return error_response("wabaId and s3Key are required")
    try:
        response = social().create_whatsapp_message_template_media(
            id=waba_id, sourceS3File={"bucketName": str(MEDIA_BUCKET), "key": s3_key})
        return success_response("eum_create_template_media", wabaId=waba_id, mediaId=response.get("mediaId"))
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_sync_templates(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    if not waba_id:
        return error_response("wabaId or metaWabaId is required")
    try:
        response = social().list_whatsapp_message_templates(id=waba_id, maxResults=100)
        templates = response.get("templates", [])
        now = iso_now()
        for tpl in templates:
            store_item({MESSAGES_PK_NAME: f"TEMPLATE_EUM#{waba_id}#{tpl.get('templateName')}", 
                       "itemType": "TEMPLATE_EUM", "wabaId": waba_id, "templateName": tpl.get("templateName"),
                       "templateStatus": tpl.get("templateStatus"), "syncedAt": now})
        return success_response("eum_sync_templates", wabaId=waba_id, syncedCount=len(templates))
    except ClientError as e:
        return error_response(str(e), 500)

def handle_eum_get_template_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    waba_id = event.get("wabaId") or _get_waba_id(event.get("metaWabaId", ""))
    template_name = event.get("templateName", "")
    if not waba_id or not template_name:
        return error_response("wabaId and templateName are required")
    item = get_item(f"TEMPLATE_EUM#{waba_id}#{template_name}")
    if not item:
        return error_response(f"Template not found: {template_name}", 404)
    return success_response("eum_get_template_status", wabaId=waba_id, templateName=template_name, status=item.get("templateStatus"))

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
