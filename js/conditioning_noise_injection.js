import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// List of node class types to target
const TARGET_NODES = [
    "ConditioningNoiseInjection", 
    "ConditioningNoiseInjectionPresets"
];

function findWorkflowParams(app) {
    const graph = app.graph;
    let foundSeed = 0;
    let foundBatchSize = 1;
    let foundSampler = false;

    function getBatchSizeFromNode(node) {
        if (node.widgets) {
            const batchWidget = node.widgets.find(w => w.name === "batch_size");
            if (batchWidget) return batchWidget.value;
        }
        return 1;
    }

    function getSourceNodeByInput(targetNode, inputName) {
        const input = targetNode.inputs?.find(i => i.name === inputName);
        if (input && input.link) {
            const link = graph.links[input.link];
            if (link) return graph._nodes_by_id[link.origin_id];
        }
        return null;
    }

    // Scan for Sampler
    for (const node of graph._nodes) {
        const nodeType = node.type || node.constructor.type;
        
        // Custom Advanced Sampler
        if (nodeType === "SamplerCustomAdvanced") {
            foundSampler = true;
            const noiseNode = getSourceNodeByInput(node, "noise");
            if (noiseNode) {
                const seedWidget = noiseNode.widgets?.find(w => w.name === "seed" || w.name === "noise_seed");
                if (seedWidget) foundSeed = seedWidget.value;
            }
            const latentNode = getSourceNodeByInput(node, "latent_image");
            if (latentNode) foundBatchSize = getBatchSizeFromNode(latentNode);
            break;
        }

        // Standard KSampler
        if (nodeType === "KSampler" || nodeType === "KSamplerAdvanced") {
            const hasModel = node.inputs?.find(i => i.name === "model" && i.link);
            if (hasModel) {
                foundSampler = true;
                const seedWidget = node.widgets?.find(w => w.name === "seed" || w.name === "noise_seed");
                if (seedWidget) foundSeed = seedWidget.value;
                const latentNode = getSourceNodeByInput(node, "latent_image");
                if (latentNode) foundBatchSize = getBatchSizeFromNode(latentNode);
                break;
            }
        }
    }
    return { seed: foundSeed, batchSize: foundBatchSize };
}

app.registerExtension({
    name: "ConditioningNoiseInjection.Sync",
    async setup() {
        const originalApiQueuePrompt = api.queuePrompt;

        api.queuePrompt = async function (number, { output, workflow }) {
            const params = findWorkflowParams(app);
            
            for (const nodeId in output) {
                const nodeData = output[nodeId];
                // Check if this node is one of our target types
                if (TARGET_NODES.includes(nodeData.class_type)) {
                    nodeData.inputs.seed_from_js = params.seed;
                    nodeData.inputs.batch_size_from_js = params.batchSize;
                }
            }
            return originalApiQueuePrompt.call(this, number, { output, workflow });
        };
    }
});
