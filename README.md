# ComfyUi-ConditioningNoiseInjectionPlus

**Advanced Conditioning Noise Injection for ComfyUI.**

I was having great success with chaining multiple [ConditioningNoiseInjection](https://github.com/BigStationW/ComfyUi-ConditioningNoiseInjection) nodes for seed variance so I quickly vibed these nodes to simulate complex chaining of noise injection. 

This extension provides tools to inject controlled random noise into your Positive or Negative conditioning. This creates variations in texture, composition, and seed variance without changing your core prompt. 

Originally, achieving these gradients required chaining multiple nodes together manually. This suite introduces **Virtual Chaining**—simulating complex stacks of nodes instantly with high performance and zero graph clutter.

---

## 1. The Dynamic Node
**`ConditioningNoiseInjectionDynamic`**

<img width="286" height="323" alt="node2" src="https://github.com/user-attachments/assets/7d5a4d40-3808-42d5-ad9d-9289f24e4688" />

Best for users who want total control. This node procedurally generates a custom decay curve based on your inputs. Enable the `show_graph` toggle to render a real-time plot of your noise schedule directly on the node. The graph updates instantly as you adjust sliders, showing exactly how the noise strength interacts with your generation steps (vertical grid lines represent steps).

### The "Chaos Factor"
Instead of setting manual thresholds, you use the **Chaos Factor** slider. This controls two variables simultaneously to maintain mathematical coherence:
1.  **Peak Strength:** How "loud" the initial noise blast is.
2.  **Duration:** How deep into the generation timeline the noise persists.

| Chaos Factor | Effect | Internal Math (Approx) |
| :--- | :--- | :--- |
| **0.0 - 0.2** | **Subtle Polish** | Peak ~3.0 | Lasts ~15% of steps |
| **0.4 - 0.6** | **Balanced Shift** | Peak ~11.0 | Lasts ~35% of steps |
| **0.8 - 1.0** | **Nuclear Chaos** | Peak ~20.0 | Lasts ~60% of steps |

### Parameters
*   **Steps:** Input your intended step count (e.g., 12). The node uses this to align the curve grid to actual sampling steps.
*   **Num Segments:** How many "simulated nodes" to chain.
    *   *Low (2):* Creates a sharp, high-contrast "Step Down" effect.
    *   *High (5+):* Creates a smooth, natural gradient decay.
*   **Strength Scale:** A global multiplier. Set to `0.0` to bypass the node.
*  **Show Graph:** Shows/hide the graph.

---

## 2. The Presets Node
**`ConditioningNoiseInjectionPresets`**

<img width="447" height="632" alt="node" src="https://github.com/user-attachments/assets/055aeafd-4be6-43f9-99c2-fb04a1ace708" />

Best for users who want curated, "tried-and-true" effects without tweaking math.

*   **Curated Recipes:** Includes specific noise schedules tuned for **9-step** (Turbo/Lightning) and **12-step** workflows.
*   **Vibe-Based Selection:** Presets range from "Subtle Polish" (texture enhancement) to "Nuclear Chaos" (major compositional hallucinations).

---

