"""Minimal Ollama HTTP client for FlashyGen.

Mirrors the pattern used in content_generation and media-content-generation —
raw requests to /api/generate rather than the ollama Python package, so there
are no transitive dependency surprises and we get full control over timeouts
and format constraints.

Env-var prefix is FG_*; falls back to CG_* so the same Ollama instance can be
shared with the other pipelines without duplicate config.
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import requests


def _envvar(name: str, default: str) -> str:
    return os.environ.get(f"FG_{name}") or os.environ.get(f"CG_{name}") or default


@dataclass
class OllamaConfig:
    model: str = "gemma3:4b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.4
    max_tokens: int = 2048
    timeout: int = 300

    @classmethod
    def from_env(cls) -> "OllamaConfig":
        return cls(
            model=_envvar("OLLAMA_MODEL", cls.model),
            base_url=_envvar("OLLAMA_URL", cls.base_url),
            temperature=float(_envvar("OLLAMA_TEMPERATURE", str(cls.temperature))),
            max_tokens=int(_envvar("OLLAMA_MAX_TOKENS", str(cls.max_tokens))),
        )


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config or OllamaConfig.from_env()

    def generate(self, prompt: str, max_tokens: int | None = None, format: str | None = None) -> str:
        url = f"{self.config.base_url}/api/generate"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
            },
        }
        if format:
            payload["format"] = format
        try:
            resp = requests.post(url, json=payload, timeout=self.config.timeout)
        except requests.ConnectionError as e:
            raise RuntimeError(
                f"Could not reach Ollama at {self.config.base_url}. "
                "Is Ollama running? Override with FG_OLLAMA_URL or CG_OLLAMA_URL."
            ) from e
        resp.raise_for_status()
        return resp.json().get("response", "")

    def generate_json_array(self, prompt: str, max_tokens: int | None = None, retries: int = 1) -> list[Any]:
        """Generate a JSON array with retry-on-parse-failure.

        format="json" constrains the sampler to valid JSON tokens — much stronger
        than prompt-only instructions. On parse failure we append a correction
        reminder and retry; the changed context shifts the sampling path.
        """
        current_prompt = prompt
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                text = self.generate(current_prompt, max_tokens=max_tokens, format="json")
                return _extract_json_array(text)
            except (json.JSONDecodeError, ValueError) as e:
                last_err = e
                if attempt >= retries:
                    break
                print(f"  ! JSON parse failed (attempt {attempt + 1}); retrying with stricter reminder")
                current_prompt = (
                    prompt
                    + "\n\nThe previous attempt produced malformed JSON. "
                    "Output STRICTLY VALID JSON ONLY: a JSON array [...] with double-quoted "
                    "keys and string values, escaped internal quotes, no trailing commas, "
                    "no comments, no prose, no markdown fences."
                )
        assert last_err is not None
        raise last_err


def _try_parse_array(text: str) -> list[Any] | None:
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    return None


def _extract_json_array(text: str) -> list[Any]:
    """Extract a JSON array from LLM output, tolerant of code-fence wrapping
    and leading/trailing prose."""
    stripped = text.strip()

    direct = _try_parse_array(stripped)
    if direct is not None:
        return direct

    # Strip markdown code fences
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", stripped, re.DOTALL)
    if fenced:
        result = _try_parse_array(fenced.group(1))
        if result is not None:
            return result

    # Find first [ ... ] span
    bracket = re.search(r"\[.*\]", stripped, re.DOTALL)
    if bracket:
        result = _try_parse_array(bracket.group(0))
        if result is not None:
            return result
        # Last-ditch: truncation recovery — close at last complete object
        raw = bracket.group(0)
        last_obj = raw.rfind("}")
        if last_obj != -1:
            recovered = raw[: last_obj + 1] + "]"
            result = _try_parse_array(recovered)
            if result is not None:
                return result

    raise ValueError(f"No JSON array found in LLM output. First 300 chars: {text[:300]}")
