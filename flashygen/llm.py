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
import time
from dataclasses import dataclass
from typing import Any

import requests


def _envvar(name: str, default: str) -> str:
    return os.environ.get(f"FG_{name}") or os.environ.get(f"CG_{name}") or default


@dataclass
class OllamaConfig:
    model: str = "huihui_ai/gemma-4-abliterated:e4b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.4
    max_tokens: int = 3072
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

    def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        format: str | None = None,
        _server_retries: int = 2,
    ) -> str:
        """POST to /api/generate with automatic retry on transient 500 errors.

        Large models that partially offload to CPU can return 500 when the GPU
        scheduler is under pressure. A short sleep between retries usually lets
        Ollama recover.
        """
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

        last_err: Exception | None = None
        for attempt in range(_server_retries + 1):
            try:
                resp = requests.post(url, json=payload, timeout=self.config.timeout)
            except requests.ConnectionError as e:
                raise RuntimeError(
                    f"Could not reach Ollama at {self.config.base_url}. "
                    "Is Ollama running? Start it with: ollama start\n"
                    "Override URL with FG_OLLAMA_URL or CG_OLLAMA_URL."
                ) from e

            if resp.status_code == 404:
                body = resp.json() if resp.content else {}
                detail = body.get("error", resp.text[:200])
                raise RuntimeError(
                    f"Ollama 404: {detail}\n"
                    f"Model '{self.config.model}' may not be pulled. "
                    f"Run: ollama pull {self.config.model}\n"
                    "Or set FG_OLLAMA_MODEL to a model you have (ollama list)."
                )

            if resp.status_code == 500 and attempt < _server_retries:
                body = resp.json() if resp.content else {}
                detail = body.get("error", "unknown server error")
                wait = 4 * (attempt + 1)
                print(f"  ! Ollama 500 (attempt {attempt + 1}): {detail} — retrying in {wait}s")
                time.sleep(wait)
                last_err = requests.HTTPError(response=resp)
                continue

            resp.raise_for_status()
            return resp.json().get("response", "")

        assert last_err is not None
        raise last_err

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
    """Try to parse text as a JSON array. Returns None on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        # Single object — model forgot the outer brackets; wrap it
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass
    return None


def _extract_json_array(text: str) -> list[Any]:
    """Extract a JSON array from LLM output.

    Handles:
    - Proper arrays: [{...}, {...}]
    - Single object without brackets: {...}  (model under-produces)
    - Markdown code fences: ```json [...] ```
    - Leading/trailing prose before the JSON
    - Truncated arrays: recover up to the last complete object
    """
    stripped = text.strip()

    # 1. Direct parse — covers both arrays and single-object responses
    direct = _try_parse_array(stripped)
    if direct is not None:
        return direct

    # 2. Fenced code block containing array or object
    fenced = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        result = _try_parse_array(fenced.group(1))
        if result is not None:
            return result

    # 3. Find first [...] span (array in surrounding prose)
    bracket = re.search(r"\[.*\]", stripped, re.DOTALL)
    if bracket:
        result = _try_parse_array(bracket.group(0))
        if result is not None:
            return result
        # Truncation recovery — close at last complete object
        raw = bracket.group(0)
        last_obj = raw.rfind("}")
        if last_obj != -1:
            recovered = raw[: last_obj + 1] + "]"
            result = _try_parse_array(recovered)
            if result is not None:
                return result

    # 4. Find first {...} span (single object in surrounding prose)
    brace = re.search(r"\{.*\}", stripped, re.DOTALL)
    if brace:
        result = _try_parse_array(brace.group(0))
        if result is not None:
            return result

    raise ValueError(f"No JSON array found in LLM output. First 300 chars: {text[:300]}")
