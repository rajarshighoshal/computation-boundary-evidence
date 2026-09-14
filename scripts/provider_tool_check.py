"""Small live GLM tool-protocol check through the existing API adapter, not a repair experiment."""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
from pathlib import Path

from scicontext.cli import _zai_coding_key
from scicontext.deepseek_agent import _api_completion, _redact_provider_text, DeepSeekProviderError
from scicontext.io import utc_now, write_json


async def check(auth_path=None):
    key = _zai_coding_key(auth_path)
    record = {"kind": "tool_protocol_check_not_repair", "model": "glm-5.3-flash", "reasoning_effort": "low",
              "api_provider": "zai-coding-plan", "started_at": utc_now(), "calls": [], "waits": [],
              "implementation_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()}
    messages = [{"role": "user", "content": "Call echo with text READY. After its result, reply exactly READY."}]
    tools = [{"type": "function", "function": {"name": "echo", "description": "Return the supplied text unchanged.",
              "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}]
    started = time.monotonic()

    async def wait(seconds):
        begin = time.monotonic()
        print(f"Provider retry: waiting {seconds}s", flush=True)
        await asyncio.sleep(seconds)
        record["waits"].append({"requested_seconds": seconds, "duration_seconds": time.monotonic() - begin})

    try:
        for turn in range(2):
            response = await _api_completion(key, record["model"], messages, tools=tools, max_tokens=1024,
                          timeout_sec=60, reasoning_effort="low", api_provider="zai-coding-plan", retry_wait=wait)
            message = response["choices"][0]["message"]
            record["calls"].append({"reported_model": response.get("model"), "attempts": response["_api_attempts"],
                                    "finish_reason": response["choices"][0].get("finish_reason"),
                                    "usage": response.get("usage"), "message": message})
            messages.append(message)
            if turn == 0:
                calls = message.get("tool_calls") or []
                if not calls:
                    raise ValueError("Model returned no tool call")
                for call in calls:
                    function = call["function"]
                    args = function.get("arguments")
                    args = args if isinstance(args, dict) else json.loads(args)
                    if function["name"] != "echo" or args != {"text": "READY"}:
                        raise ValueError("Unexpected tool request")
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": args["text"]})
            elif (message.get("content") or "").strip() != "READY" or message.get("tool_calls"):
                raise ValueError("Final answer did not match the returned tool result")
        record["status"] = "passed"
    except DeepSeekProviderError as error:
        record.update(status="provider_error", error=error.metadata)
    except Exception as error:
        record.update(status="failed", error=_redact_provider_text(error, key))
    record.update(finished_at=utc_now(), duration_seconds=time.monotonic() - started)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--auth-file", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; preserve earlier diagnostics")
    result = asyncio.run(check(args.auth_file))
    write_json(args.output, result)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "passed" else 1)
