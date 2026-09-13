"""One approved, no-retry interpretation check; not the production extractor."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter

from deepseek_extract_check import call_deepseek
from scicontext.io import digest_file, read_json, write_json

PROMPT = """Explain the task-relevant scientific computation as connected transformation units.
Group related operations across functions; describe shared conventions once. Use the supplied
code bodies, call relationships and public task documents. Distinguish what the implementation
computes from what the sources require. State concrete missing details in unknowns.

Return JSON with units (at most six), links, summary and unknowns. Each unit contains id, inputs
(array of strings), transformation (string), outputs (array of strings), conditions (array of
strings), and evidence (array of {record_id, start_line, end_line}). Evidence must cite supplied
source-body, source-entry or document IDs and supporting line ranges. Links contain source,
target and quantity, connecting unit IDs. The summary is a compact scientific explanation of
at most 250 words. Explain meaningful quantities, representation changes and relevant conditions,
not an inventory of functions. Do not propose a patch. No tools or additional files are available.

PUBLIC EVIDENCE PACKET
"""
MAX_OUTPUT = 16384
PRICE_URL = "https://api-docs.deepseek.com/quick_start/pricing/"


def prepare(source, output):
    x = read_json(source)
    p = x["evidence_packets"][0]  # Existing deterministic selection; no answer-based ranking.
    ids = set(p["object_ids"] + p["operation_ids"])
    payload = {"evidence_packets": [p],
        "objects": [o for o in x["objects"] if o["id"] in ids],
        "operations": [o for o in x["operations"] if o["id"] in ids],
        "links": [l for l in x["links"] if l["source"] in ids and l["target"] in ids],
        "context": {key: [v for v in x["context"][key] if v["id"] in p[field]]
                    for key, field in [("function_bodies", "function_body_ids"),
                        ("helper_calls", "helper_call_ids"), ("helper_gaps", "helper_gap_ids"),
                        ("code_passages", "source_entry_ids"), ("scientific_passages", "document_ids")]}}
    # Other packets can link a shared helper call to graph objects absent here.
    for call in payload["context"]["helper_calls"]:
        for key in ("caller_operation_ids", "caller_result_object_ids"):
            call[key] = [oid for oid in call[key] if oid in ids]
    prompt = PROMPT + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    bound = (len(prompt.encode()) + 1024) * 0.30 / 1e6 + MAX_OUTPUT * 1.20 / 1e6
    if bound > 0.10:
        raise ValueError("Peak-price conservative budget bound exceeds approval")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "input.json", payload)
    (output / "prompt.txt").write_text(prompt)
    config = {"source": str(source), "source_sha256": digest_file(source), "packet_id": p["id"],
        "task_id": "009", "model": "deepseek-flash", "effort": "high (provider default)",
        "max_output_tokens": MAX_OUTPUT, "attempts": 1, "retries": 0, "approved_usd": 0.10,
        "conservative_peak_bound_usd": bound, "bound_basis": "one token per UTF-8 prompt byte plus 1024 framing tokens; peak cache-miss input and maximum output",
        "pricing_url": PRICE_URL, "pricing_checked_utc": datetime.now(timezone.utc).isoformat(),
        "peak_per_million": {"cache_hit": 0.006, "cache_miss": 0.30, "output": 1.20},
        "input_sha256": digest_file(output / "input.json"), "prompt_sha256": digest_file(output / "prompt.txt"),
        "repair_runs": 0, "verifier_runs": 0, "production_changed": False}
    write_json(output / "config.json", config)
    return config


def run(output):
    config = read_json(output / "config.json")
    if (output / "attempt.json").exists():
        raise ValueError("Attempt already started; no retry is authorized")
    assert digest_file(output / "prompt.txt") == config["prompt_sha256"]
    assert digest_file(output / "input.json") == config["input_sha256"]
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise ValueError("DEEPSEEK_API_KEY is not set")
    started = datetime.now(timezone.utc)
    write_json(output / "attempt.json", {"status": "started", "started_utc": started.isoformat(), "attempt": 1})
    timer = perf_counter()
    try:
        completion = call_deepseek(key, config["model"], (output / "prompt.txt").read_text(),
                                   max_tokens=config["max_output_tokens"], timeout=900)
    except Exception as error:
        write_json(output / "receipt.json", {"status": "transport_failed", "error_type": type(error).__name__,
            "elapsed_seconds": perf_counter() - timer, "model_calls": 1, "cost_usd": None, "retries": 0})
        raise
    elapsed = perf_counter() - timer
    write_json(output / "response.json", completion)
    choice = completion["choices"][0]
    content = choice["message"].get("content") or ""
    (output / "interpretation.txt").write_text(content)
    usage = completion.get("usage", {})
    peak_cost = (usage.get("prompt_cache_hit_tokens", 0) * .006 +
                 usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0)) * .30 +
                 usage.get("completion_tokens", 0) * 1.20) / 1e6
    # Both prices retained; actual tariff can be selected from recorded UTC times.
    receipt = {"status": "response_received", "model_calls": 1, "retries": 0, "elapsed_seconds": elapsed,
        "started_utc": started.isoformat(), "finished_utc": datetime.now(timezone.utc).isoformat(),
        "requested_model": config["model"], "returned_model": completion.get("model"),
        "finish_reason": choice.get("finish_reason"), "usage": usage,
        "cost_usd_peak": peak_cost, "cost_usd_off_peak": peak_cost / 2,
        "cost_basis": "provider token usage at checked published rates, not billing invoice",
        "input_sha256": config["input_sha256"], "prompt_sha256": config["prompt_sha256"],
        "response_sha256": digest_file(output / "response.json"), "repair_runs": 0, "verifier_runs": 0}
    write_json(output / "receipt.json", receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run"])
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(args.input, args.output), indent=2))
    else:
        run(args.output)
