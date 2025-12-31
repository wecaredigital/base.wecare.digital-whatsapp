# =============================================================================
# Bedrock Integration Package
# =============================================================================
# Amazon Bedrock Agent integration for multimedia processing.
# Agent: base-wecare-digital-WhatsApp (ap-south-1)
# =============================================================================

from src.bedrock.agent import BedrockAgent
from src.bedrock.processor import BedrockProcessor
from src.bedrock.handlers import BEDROCK_HANDLERS

__all__ = [
    "BedrockAgent",
    "BedrockProcessor",
    "BEDROCK_HANDLERS",
]
