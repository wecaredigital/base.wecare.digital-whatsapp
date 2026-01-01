#!/usr/bin/env node
"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
require("source-map-support/register");
var cdk = require("aws-cdk-lib");
var base_wecare_whatsapp_stack_1 = require("../lib/base-wecare-whatsapp-stack");
var campaign_engine_stack_1 = require("../lib/campaign-engine-stack");
var eventbridge_stack_1 = require("../lib/eventbridge-stack");
var bedrock_stack_1 = require("../lib/bedrock-stack");
var agent_core_stack_1 = require("../lib/agent-core-stack");
var app = new cdk.App();
var env = {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'ap-south-1',
};
// Main infrastructure stack
var mainStack = new base_wecare_whatsapp_stack_1.BaseWecareWhatsappStack(app, 'BaseWecareWhatsappStack', {
    env: env,
    description: 'Base WECARE.DIGITAL WhatsApp Infrastructure',
});
// EventBridge stack (depends on main)
var eventBridgeStack = new eventbridge_stack_1.EventBridgeStack(app, 'EventBridgeStack', {
    env: env,
    description: 'EventBridge rules for WhatsApp events',
    mainStack: mainStack,
});
eventBridgeStack.addDependency(mainStack);
// Campaign engine stack (depends on main)
var campaignStack = new campaign_engine_stack_1.CampaignEngineStack(app, 'CampaignEngineStack', {
    env: env,
    description: 'Step Functions campaign engine',
    mainStack: mainStack,
});
campaignStack.addDependency(mainStack);
// Bedrock stack
var bedrockStack = new bedrock_stack_1.BedrockStack(app, 'BedrockStack', {
    env: env,
    description: 'Bedrock Agent and Knowledge Base',
    mainStack: mainStack,
});
bedrockStack.addDependency(mainStack);
// Agent Core stack (Amplify/Frontend API)
var agentCoreStack = new agent_core_stack_1.AgentCoreStack(app, 'AgentCoreStack', {
    env: env,
    description: 'Bedrock Agent Core API for Amplify/Frontend',
    existingBucketName: 'dev.wecare.digital',
    existingTableName: 'base-wecare-digital-whatsapp',
});
app.synth();
