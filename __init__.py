import torch

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
        # --- 9 STEP MODEL RECIPES ---
        "9-Step: Composition Kicker (Chaos Start)": [(0.35, 3.0), (0.12, 15.0)],
        "9-Step: Texture Fader (High Detail)":      [(0.45, 2.0), (0.23, 4.0)],
        "9-Step: Negative Scrambler (Fix Poses)":   [(0.55, 2.0), (0.15, 5.0)],
        "9-Step: The Steep Cliff (Cleanest)":       [(0.45, 1.0), (0.34, 3.0), (0.23, 5.0), (0.12, 8.0)],
        "9-Step: The Plateau (Stubborn Prompts)":   [(0.45, 1.0), (0.34, 2.0), (0.23, 6.0), (0.23, 6.0)],
        
        # --- 12 STEP MODEL RECIPES ---
        "12-Step: Dream Shifter (Variation)":       [(0.35, 2.0), (0.09, 12.0)],
        "12-Step: Grit Gradient (Texture)":         [(0.42, 3.0), (0.18, 5.0)],
        "12-Step: Logarithmic Decay (Natural)":     [(0.45, 1.0), (0.26, 3.0), (0.10, 8.0)],
        "12-Step: Hallucination Engine (Surreal)":  [(0.55, 2.0), (0.35, 4.0), (0.18, 6.0)],
        "12-Step: The Golden Curve (Best General)": [(0.51, 1.0), (0.34, 2.0), (0.18, 4.0), (0.09, 8.0)],
        "12-Step: The Delayed Drop (Painterly)":    [(0.51, 2.0), (0.42, 2.0), (0.26, 4.0), (0.17, 6.0)],
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

# MAPPINGS
NODE_CLASS_MAPPINGS = {
    "ConditioningNoiseInjection": ConditioningNoiseInjection, # Keep old one if needed
    "ConditioningNoiseInjectionPresets": ConditioningNoiseInjectionPresets
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ConditioningNoiseInjection": "Conditioning Noise Injection (Manual)",
    "ConditioningNoiseInjectionPresets": "Conditioning Noise Injection (Presets)"
}

WEB_DIRECTORY = "./js"
