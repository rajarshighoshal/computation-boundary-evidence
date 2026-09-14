"""Standalone paid DeepSeek reading check (no tools or container).

Uses the frozen scientific-context-input payload from a prepared run and calls
the DeepSeek chat API directly with the standard enrichment template. The only
deviation from the container flow: the payload is embedded inline instead of
readable at {scratch}, because this check has no shell tools. Everything after
the model call uses the standard compiler/join/guide. This is not the locked
experiment harness and requires separate model-call approval.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

from scicontext.io import read_json, write_json
from scicontext.object_context import ENRICHMENT_MAX_BYTES, object_bundle, render_guide
from scicontext.scientific_model import reading_input

API = "https://api.deepseek.com/chat/completions"


def call_deepseek(api_key: str, model: str, prompt: str, max_tokens: int = 16000,
                  temperature: float = 0.0, timeout: int = 900) -> dict:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    request = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-input", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--model", default="deepseek-flash")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not set")
    payload = reading_input(read_json(args.context_input))
    if len(json.dumps(payload, ensure_ascii=False).encode()) > ENRICHMENT_MAX_BYTES:
        raise ValueError("Compiled scientific input exceeds its allowance")
    graph = read_json(args.graph)
    template = (Path(__file__).resolve().parents[1] / "prompts/enrich_objects.md").read_text()
    prompt = template.format(instruction=args.instruction)
    prompt += ("\n\nEvidence JSON (no tools or file access):\n"
               + json.dumps(payload, ensure_ascii=False))
    completion = call_deepseek(api_key, args.model, prompt)
    response = completion["choices"][0]["message"]
    usage = completion.get("usage", {})
    reasoning_chars = len(response.get("reasoning_content") or "")
    receipt = {"model": args.model, "reasoning_content_chars": reasoning_chars,
               "prompt_chars": len(prompt), "context_input_bytes": len(json.dumps(payload).encode()),
               "finish_reason": completion["choices"][0].get("finish_reason"),
               "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
               "annotations_status": "no_valid_annotations"}
    text = response.get("content") or ""
    try:
        annotations = json.loads(text)
    except ValueError:
        receipt["annotations_error"] = f"response was not JSON ({len(text)} chars)"
        annotations = None
    bundle = object_bundle(graph, annotations, payload)
    receipt["annotations_status"] = bundle["assembly"]["interpretation_status"]
    receipt["applied_object_ids"] = len(bundle["assembly"]["enrichment"]["applied_object_ids"])
    receipt["dropped_invalid_enrichment"] = len(bundle["assembly"]["enrichment"]["dropped"])
    receipt["usable"] = bundle["assembly"]["usable"]
    receipt["guide_markdown_chars"] = len(render_guide(bundle["graph"]))
    write_json(args.output / "deepseek-extract-check.json", receipt)
    (args.output / "bundle.json").write_text(json.dumps(bundle, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (args.output / "scientific-guide.md").write_text(render_guide(bundle["graph"]))
    (args.output / "annotations.json").write_text(text)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
