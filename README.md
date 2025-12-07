<img width="495" height="374" alt="node" src="https://github.com/user-attachments/assets/52275088-94c6-4692-9576-6ffe84919930" />
# ComfyUi-ConditioningNoiseInjectionPresets

A fork of [ComfyUI](https://github.com/comfyanonymous/ComfyUI) that adds a node with presets dropdown to simulate chaining of the ConditioningNoiseInjection node. I was getting interesting results using certain thresholds and strengths so I quickly vibed up this preset node. Here is an explanation of how the new Preset node functions.


### 1. How the New Node Works (`ConditioningNoiseInjectionPresets`)

The original node was a "single layer" tool. To create complex effects, you had to physically chain them. The new node acts as a **Virtual Chain**. It performs the mathematical equivalent of stacking nodes without the performance overhead or graph clutter.

Here is the step-by-step logic inside `inject_noise_preset`:

#### A. The Recipe Lookup
Instead of numbers, the node receives a string key (e.g., `"9-Step: The Steep Cliff"`). It looks up the recipe in the `RECIPES` dictionary, which returns a list of "layers":
```python
# Example for "Steep Cliff"
layers = [
    (0.45, 1.0),  # Layer 1: active until 45%, strength 1.0
    (0.34, 3.0),  # Layer 2: active until 34%, strength 3.0
    (0.12, 8.0)   # Layer 3: active until 12%, strength 8.0
]
```

#### B. The "Time Slicing" Algorithm
This is the smartest part of the node. In a physical chain, Node 1 does its work, passes it to Node 2, etc. This is inefficient.
Instead, the new node **flattens the timeline**. It collects all the threshold points (`0.12`, `0.34`, `0.45`) and cuts the generation timeline (`0.0` to `1.0`) into distinct, non-overlapping segments:

1.  **Segment A:** `0.00` to `0.12`
2.  **Segment B:** `0.12` to `0.34`
3.  **Segment C:** `0.34` to `0.45`
4.  **Segment D:** `0.45` to `1.00`

#### C. Strength Summation
For each of those segments, the code calculates the **Total Strength** by checking which layers are active during that time.

*   **During Segment A (0.00 - 0.12):**
    *   Is Layer 1 active? Yes ($<0.45$). Strength +1.0
    *   Is Layer 2 active? Yes ($<0.34$). Strength +3.0
    *   Is Layer 3 active? Yes ($<0.12$). Strength +8.0
    *   **Total applied:** 12.0

*   **During Segment B (0.12 - 0.34):**
    *   Layer 1 active? Yes. (+1.0)
    *   Layer 2 active? Yes. (+3.0)
    *   Layer 3 active? **No** (Time is past 0.12).
    *   **Total applied:** 4.0

This allows the node to output a single list of conditioning chunks with the perfect strength calculated for each moment, using only **one** noise generation calculation.

---

### 2. The JavaScript Changes

The JavaScript extension is the "courier" that delivers the Seed and Batch Size from the KSampler to your node.

#### The Problem
The previous JS file was hardcoded to look for a specific class name:
```javascript
// OLD CODE
if (nodeData.class_type === "ConditioningNoiseInjection") { ... }
```
Because the new node has a *different* class name (`ConditioningNoiseInjectionPresets`), the old script would simply ignore it. The new node would sit there with `seed=0` and `batch=1`, failing to sync with your workflow.

#### The Fix
I updated the script to use an **Allowlist** approach.

1.  **Defined Targets:**
    ```javascript
    const TARGET_NODES = [
        "ConditioningNoiseInjection",         // The manual node
        "ConditioningNoiseInjectionPresets"   // The new dropdown node
    ];
    ```

2.  **Updated Logic:**
    Inside the queue interception function, it now checks if the current node exists in that list:
    ```javascript
    if (TARGET_NODES.includes(nodeData.class_type)) {
        // Inject the seed and batch size
    }
    ```
