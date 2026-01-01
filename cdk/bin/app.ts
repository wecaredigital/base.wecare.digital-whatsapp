#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { BaseWecareWhatsappStack } from '../lib/base-wecare-whatsapp-stack';
import { CampaignEngineStack } from '../lib/campaign-engine-stack';
import { EventBridgeStack } from '../lib/eventbridge-stack';
import { BedrockStack } from '../lib/bedrock-stack';
import { AgentCoreStack } from '../lib/agent-core-stack';

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: 'ap-south-1',
};

// Main infrastructure stack
const mainStack = new BaseWecareWhatsappStack(app, 'BaseWecareWhatsappStack', {
  env,
  description: 'Base WECARE.DIGITAL WhatsApp Infrastructure',
});

// EventBridge stack (depends on main)
const eventBridgeStack = new EventBridgeStack(app, 'EventBridgeStack', {
  env,
  description: 'EventBridge rules for WhatsApp events',
  mainStack,
});
eventBridgeStack.addDependency(mainStack);

// Campaign engine stack (depends on main)
const campaignStack = new CampaignEngineStack(app, 'CampaignEngineStack', {
  env,
  description: 'Step Functions campaign engine',
  mainStack,
});
campaignStack.addDependency(mainStack);

// Bedrock stack
const bedrockStack = new BedrockStack(app, 'BedrockStack', {
  env,
  description: 'Bedrock Agent and Knowledge Base',
  mainStack,
});
bedrockStack.addDependency(mainStack);

// Agent Core stack (Amplify/Frontend API)
const agentCoreStack = new AgentCoreStack(app, 'AgentCoreStack', {
  env,
  description: 'Bedrock Agent Core API for Amplify/Frontend',
  existingBucketName: 'dev.wecare.digital',
  existingTableName: 'base-wecare-digital-whatsapp',
});

app.synth();
