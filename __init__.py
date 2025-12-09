import torch
import math
import json
import os

# ============================
# PRINT TOGGLE
# ============================
DEBUG_PRINTS = False

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

        g = torch.Generator(device="cpu")
        g.manual_seed(seed_from_js)

        for i, t in enumerate(conditioning):
            original_tensor = t[0]
            original_dict = t[1].copy()
            
            current_batch_count = original_tensor.shape[0]
            target_batch_count = max(current_batch_count, batch_size_from_js)
            
            processing_tensor = original_tensor
            if current_batch_count == 1 and target_batch_count > 1:
                processing_tensor = original_tensor.repeat(target_batch_count, 1, 1)
            
            noise = torch.randn(processing_tensor.size(), generator=g, device="cpu").to(processing_tensor.device, dtype=processing_tensor.dtype)

            noisy_tensor = processing_tensor + (noise * strength)

            s_val_noise, e_val_noise = get_time_intersection(original_dict, 0.0, threshold)
            if s_val_noise < e_val_noise:
                n_noisy = [noisy_tensor, original_dict.copy()]
                n_noisy[1]["start_percent"] = s_val_noise
                n_noisy[1]["end_percent"] = e_val_noise
                c_out.append(n_noisy)

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
    # 1. LOAD JSON
    try:
        p = os.path.join(os.path.dirname(__file__), "js", "presets.json")
        with open(p, 'r', encoding='utf-8') as f:
            RECIPES = json.load(f)
    except Exception as e:
        print(f"[ConditioningNoiseInjection] Failed to load presets.json: {e}")
        RECIPES = {"Error Loading JSON": []}

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "preset": (list(s.RECIPES.keys()),),
                # ADDED STEPS INPUT
                "steps": ("INT", {"default": 12, "min": 1, "max": 100, "step": 1, "tooltip": "Total steps in your KSampler"}),
                "strength_scale": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1, "tooltip": "Multiplies the strength of the selected preset"}),
                "show_graph": ("BOOLEAN", {"default": False, "label_on": "Show Graph", "label_off": "Hide Graph"}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "seed_from_js": ("INT", {"default": 0}),
                "batch_size_from_js": ("INT", {"default": 1}),
            }
        }

    # UPDATED RETURN TYPES
    RETURN_TYPES = ("CONDITIONING", "INT")
    RETURN_NAMES = ("conditioning", "steps_out")
    FUNCTION = "inject_noise_preset"
    CATEGORY = "advanced/conditioning"

    @classmethod
    def IS_CHANGED(s, conditioning, preset, steps, strength_scale, show_graph, seed_from_js=0, batch_size_from_js=1, **kwargs):
        # Added steps to hash
        return f"{seed_from_js}_{batch_size_from_js}_{preset}_{steps}_{strength_scale}_{show_graph}"

    def inject_noise_preset(self, conditioning, preset, steps, strength_scale, show_graph, seed_from_js=0, batch_size_from_js=1, **kwargs):
        c_out = []

        raw_layers = self.RECIPES.get(preset, [])
        
        def get_time_intersection(params, limit_start, limit_end):
            old_start = params.get("start_percent", 0.0)
            old_end = params.get("end_percent", 1.0)
            new_start = max(old_start, limit_start)
            new_end = min(old_end, limit_end)
            return new_start, new_end

        g = torch.Generator(device="cpu")
        g.manual_seed(seed_from_js)

        break_points = {0.0, 1.0}
        for (thresh, _) in raw_layers:
            break_points.add(thresh)
        sorted_breaks = sorted(list(break_points))
        
        segments = []
        for i in range(len(sorted_breaks) - 1):
            segments.append((sorted_breaks[i], sorted_breaks[i+1]))

        for t in conditioning:
            original_tensor = t[0]
            original_dict = t[1].copy()

            current_batch_count = original_tensor.shape[0]
            target_batch_count = max(current_batch_count, batch_size_from_js)
            processing_tensor = original_tensor
            if current_batch_count == 1 and target_batch_count > 1:
                processing_tensor = original_tensor.repeat(target_batch_count, 1, 1)

            noise = torch.randn(processing_tensor.size(), generator=g, device="cpu").to(processing_tensor.device, dtype=processing_tensor.dtype)

            for (seg_start, seg_end) in segments:
                
                valid_start, valid_end = get_time_intersection(original_dict, seg_start, seg_end)
                
                if valid_start < valid_end:
                    total_strength_for_segment = 0.0
                    for (thresh, str_val) in raw_layers:
                        if valid_start < thresh:
                            total_strength_for_segment += str_val

                    final_strength = total_strength_for_segment * strength_scale

                    new_dict = original_dict.copy()
                    new_dict["start_percent"] = valid_start
                    new_dict["end_percent"] = valid_end

                    if final_strength > 0:
                        noisy_tensor = processing_tensor + (noise * final_strength)
                        c_out.append([noisy_tensor, new_dict])
                    else:
                        c_out.append([processing_tensor, new_dict])
            
        return (c_out, steps) # Return inputs steps directly

# ==============================================================================
# NOISE INJECTION DYNAMIC
# ==============================================================================
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
                "show_graph": ("BOOLEAN", {"default": True, "label_on": "Show Graph", "label_off": "Hide Graph"}),
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
        return f"{seed_from_js}_{batch_size_from_js}_{steps}_{num_segments}_{chaos_factor}_{strength_scale}_{show_graph}"

    def inject_dynamic(self, conditioning, steps, num_segments, chaos_factor, strength_scale, seed_from_js=0, batch_size_from_js=1, **kwargs):
        
        step_len = 1.0 / max(1, steps)
        min_duration = step_len * 1.5 
        max_duration = 0.60
        target_duration = min_duration + (max_duration - min_duration) * chaos_factor
        target_duration = min(target_duration, 1.0)

        min_peak = 2.0
        max_peak = 20.0
        peak_strength = min_peak + (max_peak - min_peak) * chaos_factor

        chunk_size = target_duration / num_segments
        segments = [] 
        
        current_time = 0.0
        
        for i in range(num_segments):
            start = current_time
            end = current_time + chunk_size
            
            progress = i / max(1, (num_segments - 1)) if num_segments > 1 else 0.0
            segment_strength = peak_strength * (1.0 - (progress * 0.9))
            final_strength = segment_strength * strength_scale
            
            segments.append((start, end, final_strength))
            current_time = end

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

            current_batch_count = original_tensor.shape[0]
            target_batch_count = max(current_batch_count, batch_size_from_js)
            processing_tensor = original_tensor
            if current_batch_count == 1 and target_batch_count > 1:
                processing_tensor = original_tensor.repeat(target_batch_count, 1, 1)

            noise = torch.randn(processing_tensor.size(), generator=g, device="cpu").to(processing_tensor.device, dtype=processing_tensor.dtype)

            last_end_time = 0.0
            
            for (seg_start, seg_end, str_val) in segments:
                
                if seg_start >= 1.0: break
                
                valid_start, valid_end = get_time_intersection(original_dict, seg_start, seg_end)
                
                if valid_start < valid_end:
                    new_dict = original_dict.copy()
                    new_dict["start_percent"] = valid_start
                    new_dict["end_percent"] = valid_end
                    
                    noisy_tensor = processing_tensor + (noise * str_val)
                    c_out.append([noisy_tensor, new_dict])
                    
                last_end_time = max(last_end_time, seg_end)

            valid_start, valid_end = get_time_intersection(original_dict, last_end_time, 1.0)
            if valid_start < valid_end:
                new_dict = original_dict.copy()
                new_dict["start_percent"] = valid_start
                new_dict["end_percent"] = valid_end
                c_out.append([processing_tensor, new_dict])

        return (c_out, steps, )

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