"""Shared utilities for parsing LLM responses."""

import json


def parse_json_response(text: str) -> dict:
    """Extract and parse JSON from an LLM response that may contain extra text.

    Tries three strategies in order:
    1. Direct JSON.parse on the stripped text
    2. Extract JSON from markdown code fences (```json ... ```)
    3. Find the outermost { ... } brace pair

    Raises ValueError if no valid JSON can be found.
    """
    stripped = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Strategy 2: markdown code fences
    if "```" in stripped:
        for block in stripped.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

    # Strategy 3: outermost braces
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {stripped[:200]}")
