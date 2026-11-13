"""One place for model calls: structured output, caching, cost, latency and a spend cap.

Two providers sit behind the same `parse()` call:
- "gemini" (default): Gemini 3.5 Flash through the Gemini API.
- "anthropic": Claude Opus 5.5 through the Anthropic API.
Choose with EXHIBIT_PROVIDER. Content is passed in one neutral shape
(text blocks and base64 PNG image blocks) and converted for each provider.

Every call is cached on disk by a hash of its full request, so a re-run costs
nothing unless a prompt, an input or the model changes. Every fresh call's
tokens, list-price cost and time go to a ledger; once the ledger's total
reaches the cap (EXHIBIT_BUDGET_USD, default $2), no further call is made.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

PROVIDERS = {
    # USD per million tokens at paid list prices. Thinking tokens bill as output.
    "gemini": {"model": "gemini-3.5-flash", "input": 1.50, "output": 9.00},
    "anthropic": {"model": "claude-opus-5-5", "input": 4.00, "output": 20.00},
}
PROVIDER = os.environ.get("EXHIBIT_PROVIDER", "gemini")
BUDGET_USD = float(os.environ.get("EXHIBIT_BUDGET_USD", "2.00"))

T = TypeVar("T", bound=BaseModel)


class BudgetExceeded(RuntimeError):
    pass


class LLM:
    def __init__(self, work_dir: Path, effort: str = "low"):
        if PROVIDER not in PROVIDERS:
            raise ValueError(f"EXHIBIT_PROVIDER must be one of {sorted(PROVIDERS)}")
        self.provider = PROVIDER
        self.model = PROVIDERS[PROVIDER]["model"]
        self.cache_dir = work_dir / "llm-cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = work_dir / "llm-ledger.jsonl"
        self.effort = effort
        self._client = None
        self.calls: list[dict] = []  # usage of every result this run used, cached or fresh

    def spent(self) -> float:
        """Total list-price spend recorded across every run that used this work folder."""
        if not self.ledger.exists():
            return 0.0
        return sum(json.loads(line)["cost_usd"] for line in self.ledger.read_text().splitlines() if line.strip())

    # ------------------------------------------------------------------ public

    def parse(self, *, task: str, system: str, content: list[dict], schema: type[T], max_tokens: int = 16000) -> T:
        request = {"provider": self.provider, "model": self.model, "effort": self.effort,
                   "system": system, "content": content, "schema": schema.model_json_schema()}
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:24]
        cached = self.cache_dir / f"{key}.json"
        if cached.exists():
            saved = json.loads(cached.read_text())
            self.calls.append({**saved["usage"], "cached": True})
            return schema.model_validate_json(saved["output"])

        spent = self.spent()
        if spent >= BUDGET_USD:
            raise BudgetExceeded(f"{task}: refusing to call the model. ${spent:.2f} already recorded, "
                                 f"cap is ${BUDGET_USD:.2f} (EXHIBIT_BUDGET_USD).")

        started = time.monotonic()
        call = self._gemini if self.provider == "gemini" else self._anthropic
        text, tokens_in, tokens_out = call(task, system, content, schema, max_tokens)
        parsed = schema.model_validate_json(text)
        price = PROVIDERS[self.provider]
        entry = {
            "task": task, "provider": self.provider, "model": self.model, "effort": self.effort,
            "seconds": round(time.monotonic() - started, 2),
            "input_tokens": tokens_in, "output_tokens": tokens_out,
            "cost_usd": round((tokens_in * price["input"] + tokens_out * price["output"]) / 1_000_000, 5),
        }
        with self.ledger.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        cached.write_text(json.dumps({"task": task, "usage": entry, "output": parsed.model_dump_json()}))
        self.calls.append({**entry, "cached": False})
        return parsed

    # ------------------------------------------------------------------ Gemini

    def _gemini(self, task, system, content, schema, max_tokens):
        from google import genai
        from google.genai import errors, types

        if self._client is None:
            self._client = genai.Client()  # reads GEMINI_API_KEY
        parts = []
        for block in content:
            if block["type"] == "text":
                parts.append(types.Part.from_text(text=block["text"]))
            else:
                src = block["source"]
                parts.append(types.Part.from_bytes(data=base64.standard_b64decode(src["data"]), mime_type=src["media_type"]))
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_tokens,
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_level=self.effort),
        )
        for attempt in range(7):
            try:
                r = self._client.models.generate_content(model=self.model, contents=[types.Content(role="user", parts=parts)], config=config)
                break
            except errors.APIError as e:
                if e.code in (429, 500, 503, 504) and attempt < 6:
                    time.sleep(min(60, 4 * 2**attempt) + random.random())
                    continue
                raise
        cand = (r.candidates or [None])[0]
        reason = getattr(cand, "finish_reason", None)
        if cand is None or not r.text:
            raise RuntimeError(f"{task}: no output (finish reason {reason}, feedback {r.prompt_feedback})")
        if str(reason).endswith("MAX_TOKENS"):
            raise RuntimeError(f"{task}: output was cut off at max_tokens={max_tokens}")
        u = r.usage_metadata
        out_tokens = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
        return r.text, u.prompt_token_count or 0, out_tokens

    # ------------------------------------------------------------------ Claude

    def _anthropic(self, task, system, content, schema, max_tokens):
        import anthropic

        if self._client is None:
            self._client = anthropic.Anthropic(max_retries=4)  # reads ANTHROPIC_API_KEY
        r = self._client.messages.parse(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": self.effort}, output_format=schema,
        )
        if r.stop_reason == "refusal":
            raise RuntimeError(f"{task}: the model declined ({r.stop_details})")
        if r.stop_reason == "max_tokens" or r.parsed_output is None:
            raise RuntimeError(f"{task}: no complete structured output (stop reason {r.stop_reason})")
        return r.parsed_output.model_dump_json(), r.usage.input_tokens, r.usage.output_tokens
