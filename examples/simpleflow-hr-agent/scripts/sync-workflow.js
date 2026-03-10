const fs = require("node:fs");
const path = require("node:path");

const workflowName = "email-chat-draft-or-clarify.yaml";
const defaultSourceRoot = "/home/rishub/Desktop/projects/rishub/SimpleFlowTestTempaltes/SimpleFlowHRAgentSystem/workflows";

const sourceRoot = String(process.env.WORKFLOW_SOURCE_ROOT || defaultSourceRoot).trim();
const sourceFile = path.resolve(sourceRoot, workflowName);
const targetFile = path.resolve(__dirname, "..", "workflows", workflowName);

if (!fs.existsSync(sourceFile)) {
  throw new Error(`Workflow source not found: ${sourceFile}`);
}

fs.mkdirSync(path.dirname(targetFile), { recursive: true });
fs.copyFileSync(sourceFile, targetFile);

console.log(`Synced workflow:`);
console.log(`- source: ${sourceFile}`);
console.log(`- target: ${targetFile}`);
