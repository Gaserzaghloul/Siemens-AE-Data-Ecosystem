# ==============================================================================
# PROMPT MANAGER
# ==============================================================================

import json
import random
import re
from collections import deque
from core.settings import PROMPT_SIZE_CYCLE, FRIENDLY_ADJECTIVES, FRIENDLY_NOUNS, STYLE_SEQUENCE
from core.prompt_templates import DIVERSE_PROMPTS, PROMPT_TEMPLATES, CATEGORY_CONTEXTS

# Global state for prompt generation
PROMPT_SIZE_INDEX = 0
PROMPT_RUN_COUNTER = 0
PROMPT_HISTORY = set()


def _friendly_token(index: int) -> str:
    """Return a human-friendly token like HorizonDrive03 based on a 1-based index."""
    if index < 1:
        index = 1
    adj_count = len(FRIENDLY_ADJECTIVES)
    noun_count = len(FRIENDLY_NOUNS)
    combo_count = adj_count * noun_count
    ordinal = (index - 1) % combo_count
    seq = (index - 1) // combo_count + 1
    adjective = FRIENDLY_ADJECTIVES[ordinal % adj_count]
    noun = FRIENDLY_NOUNS[(ordinal // adj_count) % noun_count]
    return f"{adjective}{noun}{seq:02d}"


class PromptGenerator:
    """Generate diverse prompts from templates with simple deduplication.

    Usage:
      pg = PromptGenerator()
      prompt = pg.generate('generate_core', key='SoCs')
    """

    def __init__(self, max_history=200):
        # keep a small history of generated prompts to avoid duplicates
        self.history = deque(maxlen=max_history)
        self.rng = random.Random()

    def _choose_template(self, category_key):
        templates = PROMPT_TEMPLATES.get(category_key, [])
        if not templates:
            # fallback: join all templates
            all_t = []
            for v in PROMPT_TEMPLATES.values():
                all_t.extend(v)
            templates = all_t or ["Create an AUTOSAR AE XML example focusing on {key}."]
        # random selection with slight bias to less recently used templates
        return self.rng.choice(templates)

    def generate(self, category_key, key="the requested key", max_tries=8):
        """Generate a prompt filled with `key`. Ensures it's not in recent history.

        Returns a string prompt.
        """
        for _ in range(max_tries):
            tmpl = self._choose_template(category_key)
            prompt = tmpl.format(key=key)
            # normalize whitespace for comparison
            norm = " ".join(prompt.split())
            if norm not in self.history:
                self.history.append(norm)
                return prompt
        # last resort: return a slightly modified prompt
        alt = tmpl.format(key=key) + "\n\n(Note: auto-generated variation)"
        norm = " ".join(alt.split())
        self.history.append(norm)
        return alt


_GLOBAL_PROMPT_GENERATOR = PromptGenerator()


def generate_prompt_for(category_key, key=""):
    """Convenience wrapper used by generator code.

    Ensures prompt variation and avoids recent duplicates.
    """
    return _GLOBAL_PROMPT_GENERATOR.generate(category_key, key=key)


def generate_user_prompt(key, cat_config):
    """
    Generate diverse prompts with proper size and style variation.
    Uses DIVERSE_PROMPTS templates for true variety in:
    - Size: small (50-100 words), medium (100-250 words), large (250-500 words)
    - Style: conversational, technical, user_friendly, narrative, direct
    """
    # Select size for this prompt
    global PROMPT_SIZE_INDEX
    size_bucket = PROMPT_SIZE_CYCLE[PROMPT_SIZE_INDEX % len(PROMPT_SIZE_CYCLE)]
    PROMPT_SIZE_INDEX += 1
    
    # Cycle through 5 diverse styles
    PROMPT_STYLES = ["conversational", "technical", "user_friendly", "narrative", "direct"]
    global PROMPT_RUN_COUNTER
    PROMPT_RUN_COUNTER += 1
    style = PROMPT_STYLES[PROMPT_RUN_COUNTER % len(PROMPT_STYLES)]

    # Get category context
    cat_style = cat_config.get("user_prompt_style", "generate_core") if isinstance(cat_config, dict) else "generate_core"
    context = CATEGORY_CONTEXTS.get(cat_style, key)
    
    # Generate dynamic constraints for 100% alignment
    constraints = {
        "latency_us": random.randint(10, 80),
        "power_mw": random.randint(30, 150),
        "ram_mb": random.choice([128, 256, 512, 1024]),
        "cpu_cores": random.choice([1, 2, 4, 8]),
        "period_ms": random.randint(10, 50)
    }

    # Select template from new diverse prompts
    try:
        templates = DIVERSE_PROMPTS[size_bucket][style]
        template = random.choice(templates)
        
        # Format the template with key/context and constraints
        format_args = {"key": context}
        format_args.update(constraints)
        
        # Check available placeholders in template to avoid KeyError
        placeholders = re.findall(r"\{(\w+)\}", template)
        safe_args = {pk: format_args[pk] for pk in placeholders if pk in format_args}
        prompt = template.format(**safe_args)
            
    except (KeyError, IndexError):
        # Fallback to simple prompt if templates not available
        prompt = f"Generate {key} configuration for automotive system."

    # Create unique token for metadata
    run_index = PROMPT_RUN_COUNTER
    token = _friendly_token(run_index)
    sanitized_key = re.sub(r"[^0-9A-Za-z_]", "_", key.replace(" ", "_"))
    if not re.match(r"[A-Za-z_]", sanitized_key):
        sanitized_key = f"P_{sanitized_key}"
    uniq_prefix = f"{sanitized_key}_{token}"

    # Dedup check
    signature = " ".join(prompt.split())
    if signature in PROMPT_HISTORY:
        prompt += f"\n\n[Variant:{token}] Provide unique verification checklist."
        signature = " ".join(prompt.split())
    PROMPT_HISTORY.add(signature)

    # Attach machine-readable metadata
    meta_payload = {
        "prefix": uniq_prefix,
        "size": size_bucket,
        "style": style,
        "key": key,
    }
    meta_payload.update(constraints)
    prompt_with_meta = (
        f"{prompt}\n\n[[PROMPT_META {json.dumps(meta_payload, sort_keys=True)}]]"
    )

    return prompt_with_meta


def get_prompt_count():
    """Get the total number of available prompts across all categories."""
    total_count = 0
    for category_prompts in PROMPT_TEMPLATES.values():
        total_count += len(category_prompts)
    return total_count


def get_category_prompt_count(category_style):
    """Get the number of prompts available for a specific category."""
    return len(PROMPT_TEMPLATES.get(category_style, []))


def list_available_categories():
    """List all available prompt categories."""
    return list(PROMPT_TEMPLATES.keys())


# Seeding and history management helpers (for deduplication across runs)


def set_prompt_seed(seed):
    """
    Set the random seed used by the global prompt generator.
    Accepts any int-like value. Calling this makes prompt generation
    deterministic for a given seed within the current process.
    """
    try:
        _GLOBAL_PROMPT_GENERATOR.rng.seed(int(seed))
    except Exception:
        # Fall back to string-based seed
        _GLOBAL_PROMPT_GENERATOR.rng.seed(str(seed))


def reset_prompt_history():
    """
    Clear the recent-prompt history used to avoid near-term duplicates.
    Useful between runs when you want a fresh dedup window.
    """
    try:
        _GLOBAL_PROMPT_GENERATOR.history.clear()
    except Exception:
        pass


def get_prompt_history_size():
    """Return the current number of prompts stored in dedup history."""
    try:
        return len(_GLOBAL_PROMPT_GENERATOR.history)
    except Exception:
        return 0
