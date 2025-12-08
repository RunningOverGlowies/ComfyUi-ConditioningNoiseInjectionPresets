import torch
import math

# ============================
# PRINT TOGGLE
# ============================
DEBUG_PRINTS = False  # ← set to True to enable all prints


def debug_print(*args, **kwargs):
    if DEBUG_PRINTS:
        print(*args, **kwargs)


class ConditioningNoiseInjection:
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "threshold": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.01}),
                "strength": ("FLOAT", {"default": 10, "min": 0.0, "max": 100.0, "step": 1.0}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "seed_from_js": ("INT", {"default": 0}),
                "batch_size_from_js": ("INT", {"default": 1}),
            }
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "inject_noise"
    CATEGORY = "advanced/conditioning"

    @classmethod
    def IS_CHANGED(s, conditioning, threshold, strength, seed_from_js=0, batch_size_from_js=1, **kwargs):
        # We include batch_size in the hash to ensure updates when batch size changes
        return f"{seed_from_js}_{batch_size_from_js}_{threshold}_{strength}"

    def inject_noise(self, conditioning, threshold, strength, seed_from_js=0, batch_size_from_js=1, **kwargs):
        debug_print(f"\n[NoiseInjection] Base Seed: {seed_from_js}, Target Batch Size: {batch_size_from_js}")

        c_out = []

        def get_time_intersection(params, limit_start, limit_end):
            old_start = params.get("start_percent", 0.0)
            old_end = params.get("end_percent", 1.0)
            new_start = max(old_start, limit_start)
            new_end = min(old_end, limit_end)
            if new_start >= new_end:
                return 1.0, 0.0
            return new_start, new_end

        # Standard ComfyUI CPU Generator for reproducibility
        g = torch.Generator(device="cpu")
        g.manual_seed(seed_from_js)

        for i, t in enumerate(conditioning):
            original_tensor = t[0] # Shape [Batch, Tokens, Channels] or [1, T, C]
            original_dict = t[1].copy()
            
            # 1. Handle Batch Expansion
            # If the input is Batch 1 (common for conditioning), but the workflow is Batch N,
            # we repeat the tensor to match.
            current_batch_count = original_tensor.shape[0]
            target_batch_count = max(current_batch_count, batch_size_from_js)
            
            processing_tensor = original_tensor
            if current_batch_count == 1 and target_batch_count > 1:
                # [1, T, C] -> [N, T, C]
                processing_tensor = original_tensor.repeat(target_batch_count, 1, 1)
            
            # 2. Generate Noise (Native ComfyUI Method)
            # We generate one large noise tensor for the whole batch at once.
            # This ensures Image 2 gets the "next" sequence of random numbers, consistent with KSampler.
            noise = torch.randn(
                processing_tensor.size(),
                generator=g,
                device="cpu"
            ).to(
                processing_tensor.device,
                dtype=processing_tensor.dtype
            )

            # --- VERIFICATION PRINTS ---
            debug_print(f"--- Conditioning Group {i} Noise Values ---")
            for b in range(target_batch_count):
                # Get the first few float values of the first token for this batch item
                # noise[b] is shape [Tokens, Channels]
                first_vals = noise[b, 0, :5].tolist()
                formatted_vals = [f"{x:+.4f}" for x in first_vals]
                debug_print(f"   > Batch Index {b}: {formatted_vals} ...")
            # ---------------------------

            # Apply noise
            noisy_tensor = processing_tensor + (noise * strength)

            # 3. Time Intersection & Output
            # Noisy Part (Start -> Threshold)
            s_val_noise, e_val_noise = get_time_intersection(original_dict, 0.0, threshold)
            if s_val_noise < e_val_noise:
                n_noisy = [noisy_tensor, original_dict.copy()]
                n_noisy[1]["start_percent"] = s_val_noise
                n_noisy[1]["end_percent"] = e_val_noise
                c_out.append(n_noisy)

            # Clean Part (Threshold -> End)
            s_val_clean, e_val_clean = get_time_intersection(original_dict, threshold, 1.0)
            if s_val_clean < e_val_clean:
                n_clean = [processing_tensor, original_dict.copy()]
                n_clean[1]["start_percent"] = s_val_clean
                n_clean[1]["end_percent"] = e_val_clean
                c_out.append(n_clean)

        return (c_out, )


# ==============================================================================
# NOISE INJECTION PRESETS
# ==============================================================================
class ConditioningNoiseInjectionPresets:
    
    # --------------------------------------------------------------------------
    # RECIPE LIBRARY
    # Format: "Name": [(Threshold, Strength), (Threshold, Strength), ...]
    # --------------------------------------------------------------------------
    RECIPES = {
        "Disabled": [],
        # ======================================================================
        # TIER 1: SUBTLE & POLISH (Safe)
        # Low strength, mostly for texture or micro-details.
        # ======================================================================
        "🟢 Cinematic Haze (Texture Only)":    [(0.55, 0.5), (0.44, 0.5), (0.33, 1.0)],
        "🟢 Texture Fader (High Detail)":      [(0.45, 2.0), (0.23, 4.0)],
        "🟢 The Fluid Half":                   [(0.50, 1.5), (0.22, 3.0)],
        "🟢 Portrait Skin Saver":             [(0.34, 0.5), (0.26, 1.0), (0.17, 3.0), (0.09, 5.0)],
        "🟢 The Perfect Slope":               [(0.34, 1.0), (0.26, 1.0), (0.17, 1.0), (0.09, 1.0)],

        # ======================================================================
        # TIER 2: BALANCED (Standard)
        # Good initial kick to set composition, but cleans up nicely.
        # ======================================================================
        "🟡 The Steep Cliff (Cleanest)":       [(0.45, 1.0), (0.34, 3.0), (0.23, 5.0), (0.12, 8.0)],
        "🟡 Hard Cut (Contrast)":              [(0.33, 4.0), (0.33, 2.0)],
        "🟡 Logarithmic Decay (Natural)":     [(0.45, 1.0), (0.26, 3.0), (0.10, 8.0)],
        "🟡 The Golden Curve (Best General)": [(0.51, 1.0), (0.34, 2.0), (0.18, 4.0), (0.09, 8.0)],

        # ======================================================================
        # TIER 3: STRONG & STYLISTIC (Noticeable Alteration)
        # Heavier textures or noise that lingers longer into the generation.
        # ======================================================================
        "🟠 Negative Scrambler (Fix Poses)":   [(0.55, 2.0), (0.15, 5.0)],
        "🟠 Painterly Softness (Late Noise)":  [(0.66, 1.0), (0.33, 2.0)],
        "🟠 Grit Gradient (Texture)":         [(0.42, 3.0), (0.18, 5.0)],
        "🟠 The Delayed Drop (Painterly)":    [(0.51, 2.0), (0.42, 2.0), (0.26, 4.0), (0.17, 6.0)],
        "🟠 Hallucination Engine (Surreal)":  [(0.55, 2.0), (0.35, 4.0), (0.18, 6.0)],

        # ======================================================================
        # TIER 4: HEAVY DISTORTION (Major Changes)
        # Sustained high noise or long durations. Changes the prompt significantly.
        # ======================================================================
        "🔴 Detail Scrambler":                 [(0.34, 2.0), (0.23, 4.0), (0.23, 4.0)],
        "🔴 The Plateau (Stubborn Prompts)":   [(0.45, 1.0), (0.34, 2.0), (0.23, 6.0), (0.23, 6.0)],
        "🔴 Surreal Melt":                    [(0.51, 2.0), (0.51, 2.0)],
        "🔴 Deep Fryer":                      [(0.25, 4.0), (0.25, 4.0)],

        # ======================================================================
        # TIER 5: NUCLEAR (Chaos & Hallucinations)
        # Massive strength spikes. Expect aliens, glitches, and wild geometry.
        # ======================================================================
        "🤡 Composition Kicker (Chaos Start)": [(0.35, 3.0), (0.12, 15.0)],
        "🤡 The Nuclear Option":               [(0.12, 25.0), (0.23, 2.0)],
        "🤡 The Hiccup":                      [(0.17, 10.0), (0.25, 1.0)],
        "🤡 Dream Shifter (Variation)":       [(0.35, 2.0), (0.09, 12.0)],
        "🤡 Composition Lock":                [(0.17, 10.0), (0.09, 5.0)],
    }

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "preset": (list(s.RECIPES.keys()),),
                "strength_scale": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1, "tooltip": "Multiplies the strength of the selected preset"}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "seed_from_js": ("INT", {"default": 0}),
                "batch_size_from_js": ("INT", {"default": 1}),
            }
        }

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "inject_noise_preset"
    CATEGORY = "advanced/conditioning"

    @classmethod
    def IS_CHANGED(s, conditioning, preset, strength_scale, seed_from_js=0, batch_size_from_js=1, **kwargs):
        return f"{seed_from_js}_{batch_size_from_js}_{preset}_{strength_scale}"

    def inject_noise_preset(self, conditioning, preset, strength_scale, seed_from_js=0, batch_size_from_js=1, **kwargs):
        c_out = []

        # 1. Retrieve the layers for the selected recipe
        # Format: [(threshold, strength), ...]
        raw_layers = self.RECIPES.get(preset, [])
        
        # 2. Define Time Utility
        def get_time_intersection(params, limit_start, limit_end):
            old_start = params.get("start_percent", 0.0)
            old_end = params.get("end_percent", 1.0)
            new_start = max(old_start, limit_start)
            new_end = min(old_end, limit_end)
            return new_start, new_end

        # 3. Setup Noise Generator
        g = torch.Generator(device="cpu")
        g.manual_seed(seed_from_js)

        # 4. Calculate Time Segments
        # We need to slice the timeline (0.0 to 1.0) into chunks based on all thresholds
        break_points = {0.0, 1.0}
        for (thresh, _) in raw_layers:
            break_points.add(thresh)
        sorted_breaks = sorted(list(break_points))
        
        # Create segments: [(0.0, 0.1), (0.1, 0.35), etc...]
        segments = []
        for i in range(len(sorted_breaks) - 1):
            segments.append((sorted_breaks[i], sorted_breaks[i+1]))

        # 5. Process Conditioning
        for t in conditioning:
            original_tensor = t[0]
            original_dict = t[1].copy()

            # --- Batch Expansion Logic ---
            current_batch_count = original_tensor.shape[0]
            target_batch_count = max(current_batch_count, batch_size_from_js)
            processing_tensor = original_tensor
            if current_batch_count == 1 and target_batch_count > 1:
                processing_tensor = original_tensor.repeat(target_batch_count, 1, 1)

            # --- Generate Noise ---
            # Single noise pattern for the whole generation
            noise = torch.randn(processing_tensor.size(), generator=g, device="cpu").to(processing_tensor.device, dtype=processing_tensor.dtype)

            # --- Iterate Time Segments ---
            for (seg_start, seg_end) in segments:
                
                # Check if this segment exists within the input conditioning's timeframe
                valid_start, valid_end = get_time_intersection(original_dict, seg_start, seg_end)
                
                if valid_start < valid_end:
                    # Calculate Total Strength for this specific time segment
                    # A layer is active if the segment falls *before* the layer's threshold
                    # Since we split exactly at thresholds, we check if segment_start < threshold
                    total_strength_for_segment = 0.0
                    for (thresh, str_val) in raw_layers:
                        if valid_start < thresh:
                            total_strength_for_segment += str_val

                    # Apply Scaling
                    final_strength = total_strength_for_segment * strength_scale

                    # Create Output
                    new_dict = original_dict.copy()
                    new_dict["start_percent"] = valid_start
                    new_dict["end_percent"] = valid_end

                    if final_strength > 0:
                        noisy_tensor = processing_tensor + (noise * final_strength)
                        c_out.append([noisy_tensor, new_dict])
                    else:
                        c_out.append([processing_tensor, new_dict])
            
        return (c_out, )

class ConditioningNoiseInjectionDynamic:
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "steps": ("INT", {"default": 9, "min": 1, "max": 100, "step": 1, "tooltip": "Total steps in your KSampler"}),
                "num_segments": ("INT", {"default": 3, "min": 1, "max": 10, "step": 1, "tooltip": "How many 'simulated nodes' to chain"}),
                "chaos_factor": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "0.0 = Subtle Polish, 1.0 = Nuclear Chaos"}),
                "strength_scale": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1, "tooltip": "Global multiplier"}),
                "show_graph": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "seed_from_js": ("INT", {"default": 0}),
                "batch_size_from_js": ("INT", {"default": 1}),
            }
        }

    RETURN_TYPES = ("CONDITIONING", "INT")
    RETURN_NAMES = ("conditioning", "steps_out")
    FUNCTION = "inject_dynamic"
    CATEGORY = "advanced/conditioning"

    @classmethod
    def IS_CHANGED(s, conditioning, steps, num_segments, chaos_factor, strength_scale, show_graph, seed_from_js=0, batch_size_from_js=1, **kwargs):
        # Include all curve parameters in hash
        return f"{seed_from_js}_{batch_size_from_js}_{steps}_{num_segments}_{chaos_factor}_{strength_scale}_{show_graph}"

    def inject_dynamic(self, conditioning, steps, num_segments, chaos_factor, strength_scale, seed_from_js=0, batch_size_from_js=1, **kwargs):
        
        # ======================================================================
        # 1. PROCEDURAL CURVE GENERATION
        # ======================================================================
        
        # Calculate single step duration
        step_len = 1.0 / max(1, steps)
        
        # A. Determine Max Duration (How deep into generation we go)
        # Low Chaos (0.0) -> Lasts ~15% of steps (or min 2 steps)
        # High Chaos (1.0) -> Lasts ~60% of steps
        min_duration = step_len * 1.5 
        max_duration = 0.60
        target_duration = min_duration + (max_duration - min_duration) * chaos_factor
        
        # Clamp duration to 1.0
        target_duration = min(target_duration, 1.0)

        # B. Determine Peak Strength (The strength of the first segment)
        # Low Chaos (0.0) -> 2.0
        # High Chaos (1.0) -> 20.0
        min_peak = 2.0
        max_peak = 20.0
        peak_strength = min_peak + (max_peak - min_peak) * chaos_factor

        # C. Generate Segments
        # We slice the 'target_duration' into 'num_segments' chunks.
        # We linearly decay the strength from Peak -> Low.
        
        chunk_size = target_duration / num_segments
        segments = [] # List of (start_time, end_time, strength_val)
        
        current_time = 0.0
        
        for i in range(num_segments):
            start = current_time
            end = current_time + chunk_size
            
            # Calculate Strength for this chunk
            # Simple Linear Decay formula:
            # Segment 0 = Peak
            # Segment Last = ~10% of Peak
            progress = i / max(1, (num_segments - 1)) if num_segments > 1 else 0.0
            
            # Curve: Linear decay
            segment_strength = peak_strength * (1.0 - (progress * 0.9))
            
            # Apply Global Scale
            final_strength = segment_strength * strength_scale
            
            segments.append((start, end, final_strength))
            current_time = end

        # ======================================================================
        # 2. NOISE INJECTION LOGIC (Flattened Timeline)
        # ======================================================================
        
        c_out = []

        def get_time_intersection(params, limit_start, limit_end):
            old_start = params.get("start_percent", 0.0)
            old_end = params.get("end_percent", 1.0)
            new_start = max(old_start, limit_start)
            new_end = min(old_end, limit_end)
            return new_start, new_end

        g = torch.Generator(device="cpu")
        g.manual_seed(seed_from_js)

        for t in conditioning:
            original_tensor = t[0]
            original_dict = t[1].copy()

            # Batch Expansion
            current_batch_count = original_tensor.shape[0]
            target_batch_count = max(current_batch_count, batch_size_from_js)
            processing_tensor = original_tensor
            if current_batch_count == 1 and target_batch_count > 1:
                processing_tensor = original_tensor.repeat(target_batch_count, 1, 1)

            # Generate Noise (Once per conditioning item)
            noise = torch.randn(processing_tensor.size(), generator=g, device="cpu").to(processing_tensor.device, dtype=processing_tensor.dtype)

            # --- Apply Segments ---
            # Any gap between segments (e.g., after the last segment) needs to be filled with Clean conditioning
            
            last_end_time = 0.0
            
            # 1. Apply Noisy Segments
            for (seg_start, seg_end, str_val) in segments:
                
                # Verify we aren't overlapping floating point weirdness
                if seg_start >= 1.0: break
                
                valid_start, valid_end = get_time_intersection(original_dict, seg_start, seg_end)
                
                if valid_start < valid_end:
                    new_dict = original_dict.copy()
                    new_dict["start_percent"] = valid_start
                    new_dict["end_percent"] = valid_end
                    
                    noisy_tensor = processing_tensor + (noise * str_val)
                    c_out.append([noisy_tensor, new_dict])
                    
                last_end_time = max(last_end_time, seg_end)

            # 2. Apply Clean Tail (The rest of generation)
            # If our segments ended at 0.4, we need clean from 0.4 to 1.0
            valid_start, valid_end = get_time_intersection(original_dict, last_end_time, 1.0)
            if valid_start < valid_end:
                new_dict = original_dict.copy()
                new_dict["start_percent"] = valid_start
                new_dict["end_percent"] = valid_end
                c_out.append([processing_tensor, new_dict])

        return (c_out, steps, )

# MAPPINGS UPDATE
NODE_CLASS_MAPPINGS = {
    "ConditioningNoiseInjection": ConditioningNoiseInjection,
    "ConditioningNoiseInjectionPresets": ConditioningNoiseInjectionPresets,
    "ConditioningNoiseInjectionDynamic": ConditioningNoiseInjectionDynamic,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ConditioningNoiseInjection": "Conditioning Noise Injection (Manual)",
    "ConditioningNoiseInjectionPresets": "Conditioning Noise Injection (Presets)",
    "ConditioningNoiseInjectionDynamic": "Conditioning Noise Injection (Dynamic)",
}

WEB_DIRECTORY = "./js"
