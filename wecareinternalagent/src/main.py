"""
WECARE.DIGITAL Internal Agent - Task Automation for Amplify
Deployed via AWS Bedrock AgentCore in ap-south-1.
"""
import os
import json
import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
log = app.logger

REGION = os.getenv("AWS_REGION", "ap-south-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-2-lite-v1:0")

_bedrock = None

def get_bedrock():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    return _bedrock

SYSTEM = """You are WECARE.DIGITAL Internal Assistant. Brands: BNB CLUB (Travel), NO FAULT (ODR), EXPO WEEK (Events), RITUAL GURU (Puja), LEGAL CHAMP (Docs), SWDHYA (Conversations). Be helpful and concise."""

@app.entrypoint
async def invoke(payload, context):
    prompt = payload.get("prompt", "")
    log.info(f"Processing: {prompt[:50]}...")
    
    bedrock = get_bedrock()
    # Amazon Nova uses Converse API format
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "system": [{"text": SYSTEM}],
        "inferenceConfig": {"maxTokens": 1024, "temperature": 0.7}
    })
    
    response = bedrock.invoke_model(modelId=MODEL_ID, body=body)
    result = json.loads(response["body"].read())
    # Nova response format
    text = result.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "No response")
    yield text

if __name__ == "__main__":
    app.run()
