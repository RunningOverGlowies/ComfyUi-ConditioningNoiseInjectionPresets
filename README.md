# ComfyUi-ConditioningNoiseInjectionPlus

**Advanced Conditioning Noise Injection for ComfyUI.**

I was having great success with chaining multiple [ConditioningNoiseInjection](https://github.com/BigStationW/ComfyUi-ConditioningNoiseInjection) nodes for seed variance so I quickly vibed these nodes to simulate complex chains of noise injection. 

This extension provides tools to inject controlled random noise into your Positive or Negative conditioning. This creates variations in texture, composition, and seed variance without changing your core prompt. 


---

## 1. The Dynamic Node
**`ConditioningNoiseInjectionDynamic`**

<img width="362" height="390" alt="t" src="https://github.com/user-attachments/assets/4392224f-3baf-489f-a772-432d91c7bec8" />

This node procedurally generates a custom decay curve based on your inputs. Enable the `show_graph` toggle to render a real-time plot of your noise. The graph updates as you adjust sliders, showing how the noise strength interacts with your generation steps (vertical grid lines represent steps). 

The graph includes a green box indicating a 'Safe Zone' (Strength < 16.45, Duration < 37%). In my limited experimentation keeping your curve within this box generally ensures coherent results (this is entirely subject, your mileage may vary).

### The "Chaos Factor"
The **Chaos Factor** slider controls two variables simultaneously to maintain mathematical coherence:
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

