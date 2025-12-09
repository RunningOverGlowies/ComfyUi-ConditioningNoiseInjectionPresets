import { app } from "../../scripts/app.js";

// List of node class types
const TARGET_NODES = [
    "ConditioningNoiseInjection", 
    "ConditioningNoiseInjectionPresets",
    "ConditioningNoiseInjectionDynamic"
];

let PRESET_DATA = {};

// Fetch the JSON file located in the same directory as this script
try {
    const response = await fetch(new URL("./presets.json", import.meta.url));
    PRESET_DATA = await response.json();
} catch (e) {
    console.error("[ConditioningNoiseInjection] Failed to load presets.json", e);
}

// =============================================================================
// HELPER: WORKFLOW SYNC
// =============================================================================
function findWorkflowParams(app) {
    const graph = app.graph;
    let foundSeed = 0;
    let foundBatchSize = 1;

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

    for (const node of graph._nodes) {
        const nodeType = node.type || node.constructor.type;
        if (nodeType === "SamplerCustomAdvanced") {
            const noiseNode = getSourceNodeByInput(node, "noise");
            if (noiseNode) {
                const seedWidget = noiseNode.widgets?.find(w => w.name === "seed" || w.name === "noise_seed");
                if (seedWidget) foundSeed = seedWidget.value;
            }
            const latentNode = getSourceNodeByInput(node, "latent_image");
            if (latentNode) foundBatchSize = getBatchSizeFromNode(latentNode);
            break;
        }
        if (nodeType === "KSampler" || nodeType === "KSamplerAdvanced") {
            const hasModel = node.inputs?.find(i => i.name === "model" && i.link);
            if (hasModel) {
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

// =============================================================================
// HELPER: GRAPH CALCULATIONS
// =============================================================================

function calculateDynamicGraph(steps, num_segments, chaos_factor, strength_scale) {
    const step_len = 1.0 / Math.max(1, steps);
    const min_duration = step_len * 1.5;
    const max_duration = 0.60;
    
    let target_duration = min_duration + (max_duration - min_duration) * chaos_factor;
    target_duration = Math.min(target_duration, 1.0);

    const min_peak = 2.0;
    const max_peak = 20.0;
    const peak_strength = min_peak + (max_peak - min_peak) * chaos_factor;

    const chunk_size = target_duration / num_segments;
    const points = []; 

    let current_time = 0.0;
    let foundMax = 0; // Track the highest point

    for (let i = 0; i < num_segments; i++) {
        const start = current_time;
        const end = current_time + chunk_size;
        
        const progress = (num_segments > 1) ? (i / (num_segments - 1)) : 0.0;
        const segment_strength = peak_strength * (1.0 - (progress * 0.9));
        const final_strength = segment_strength * strength_scale;

        // Track Max
        if (final_strength > foundMax) foundMax = final_strength;

        points.push({ x: start, y: final_strength });
        points.push({ x: end, y: final_strength });
        current_time = end;
    }
    points.push({ x: current_time, y: 0 });
    points.push({ x: 1.0, y: 0 });

    return { points, maxY: Math.max(25.0, foundMax + 5.0) };
}

function calculatePresetGraph(presetName, strength_scale) {
    const layers = PRESET_DATA[presetName] || [];
    
    // 1. Find Break Points
    const breaks = new Set([0.0, 1.0]);
    layers.forEach(l => breaks.add(l[0])); 
    const sortedBreaks = Array.from(breaks).sort((a, b) => a - b);
    
    const points = [];
    let maxY = 15.0; 

    // 2. Iterate Segments
    for(let i=0; i<sortedBreaks.length - 1; i++) {
        const start = sortedBreaks[i];
        const end = sortedBreaks[i+1];
        
        let totalStrength = 0;
        layers.forEach(l => {
            const thresh = l[0];
            const str = l[1];
            if(start < thresh) {
                totalStrength += str;
            }
        });

        const finalStrength = totalStrength * strength_scale;
        if(finalStrength > maxY) maxY = finalStrength + 5;

        points.push({ x: start, y: finalStrength });
        points.push({ x: end, y: finalStrength });
    }

    return { points, maxY: Math.max(25.0, maxY) };
}

// =============================================================================
// HELPER: COMMON DRAWING FUNCTION
// =============================================================================
function drawNodeGraph(ctx, size, data, stepCount) {
    const graphHeight = 120;
    const margin = 10;
    const areaX = margin;
    const areaY = size[1] - graphHeight - margin;
    const areaW = size[0] - (margin * 2);
    const areaH = graphHeight;

    // 1. Background
    ctx.fillStyle = "#111";
    ctx.fillRect(areaX, areaY, areaW, areaH);
    ctx.strokeStyle = "#333";
    ctx.strokeRect(areaX, areaY, areaW, areaH);

    // 2. Safe Zone
    const safeTime = 0.37;
    const safeStrength = 16.45;
    const maxY = data.maxY;
    const safeW = areaW * safeTime;
    const safeH = (safeStrength / maxY) * areaH;
    const safeY = (areaY + areaH) - safeH;

    ctx.fillStyle = "rgba(0, 255, 100, 0.05)"; 
    ctx.fillRect(areaX, safeY, safeW, safeH);
    
    ctx.strokeStyle = "rgba(0, 255, 100, 0.4)";
    ctx.setLineDash([4, 4]); 
    ctx.strokeRect(areaX, safeY, safeW, safeH);
    ctx.setLineDash([]);

    ctx.fillStyle = "rgba(0, 255, 100, 0.8)";
    ctx.font = "9px Arial";
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    ctx.fillText("SAFE ZONE", areaX + 4, safeY - 2);

    // 3. Grid
    ctx.beginPath();
    ctx.strokeStyle = "#2a2a2a";
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);
    
    const gridDivs = stepCount > 0 ? stepCount : 10;
    
    for(let i=1; i<gridDivs; i++) {
        const x = areaX + (areaW * (i / gridDivs));
        ctx.moveTo(x, areaY);
        ctx.lineTo(x, areaY + areaH);
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // 4. Curve
    ctx.beginPath();
    ctx.strokeStyle = "#5577ff";
    ctx.lineWidth = 2;
    for(let i=0; i<data.points.length; i++) {
        const p = data.points[i];
        const px = areaX + (p.x * areaW);
        const py = (areaY + areaH) - ((p.y / maxY) * areaH);
        if(i===0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
    }
    ctx.stroke();

    // 5. Axes Labels
    ctx.fillStyle = "rgba(200, 200, 200, 0.6)";
    ctx.font = "9px Arial";
    
    // Top
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(`${maxY.toFixed(1)}`, areaX + 4, areaY + 4);

    // Bottom
    ctx.textBaseline = "bottom";
    ctx.fillText("0.0", areaX + 4, areaY + areaH - 4);
    
    // Right
    ctx.textAlign = "right";
    ctx.fillText("1.0", areaX + areaW - 4, areaY + areaH - 4);

    // Center
    ctx.textAlign = "center";
    ctx.fillStyle = "rgba(200, 200, 200, 0.3)";
    ctx.fillText(stepCount > 0 ? "STEPS" : "PROGRESS", areaX + (areaW / 2), areaY + areaH - 4);
}

// =============================================================================
// MAIN EXTENSION
// =============================================================================
app.registerExtension({
    name: "ConditioningNoiseInjection.SyncAndGraph",
    
    async setup() {
        const originalApiQueuePrompt = api.queuePrompt;
        api.queuePrompt = async function (number, { output, workflow }) {
            const params = findWorkflowParams(app);
            for (const nodeId in output) {
                const nodeData = output[nodeId];
                if (TARGET_NODES.includes(nodeData.class_type)) {
                    nodeData.inputs.seed_from_js = params.seed;
                    nodeData.inputs.batch_size_from_js = params.batchSize;
                }
            }
            return originalApiQueuePrompt.call(this, number, { output, workflow });
        };
    },

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        
        // ---------------------------------------------------------------------
        // HANDLER FOR DYNAMIC NODE
        // ---------------------------------------------------------------------
        if (nodeData.name === "ConditioningNoiseInjectionDynamic") {
            const onDrawForeground = nodeType.prototype.onDrawForeground;
            nodeType.prototype.onDrawForeground = function(ctx) {
                if (onDrawForeground) onDrawForeground.apply(this, arguments);
                
                const w_graph = this.widgets.find(w => w.name === "show_graph");
                if (!w_graph || !w_graph.value) return;

                if (this.size[1] < 300 && this.flags.collapsed !== true) {
                    this.setSize([this.size[0], 300]);
                }

                const w_steps = this.widgets.find(w => w.name === "steps");
                const w_segs = this.widgets.find(w => w.name === "num_segments");
                const w_chaos = this.widgets.find(w => w.name === "chaos_factor");
                const w_scale = this.widgets.find(w => w.name === "strength_scale");

                if (!w_steps || !w_segs || !w_chaos || !w_scale) return;

                const data = calculateDynamicGraph(w_steps.value, w_segs.value, w_chaos.value, w_scale.value);
                
                ctx.save();
                drawNodeGraph(ctx, this.size, data, w_steps.value);
                ctx.restore();
            }
        }

        // ---------------------------------------------------------------------
        // HANDLER FOR PRESETS NODE
        // ---------------------------------------------------------------------
        if (nodeData.name === "ConditioningNoiseInjectionPresets") {
            const onDrawForeground = nodeType.prototype.onDrawForeground;
            nodeType.prototype.onDrawForeground = function(ctx) {
                if (onDrawForeground) onDrawForeground.apply(this, arguments);

                const w_graph = this.widgets.find(w => w.name === "show_graph");
                if (!w_graph || !w_graph.value) return;

                if (this.size[1] < 275 && this.flags.collapsed !== true) {
                    this.setSize([this.size[0], 275]);
                }

                const w_preset = this.widgets.find(w => w.name === "preset");
                const w_scale = this.widgets.find(w => w.name === "strength_scale");
                
                // UPDATED: Find Steps widget now
                const w_steps = this.widgets.find(w => w.name === "steps");

                if(!w_preset || !w_scale || !w_steps) return;

                const data = calculatePresetGraph(w_preset.value, w_scale.value);

                // UPDATED: Pass w_steps.value instead of guessing logic
                ctx.save();
                drawNodeGraph(ctx, this.size, data, w_steps.value);
                ctx.restore();
            }
        }
    }
});