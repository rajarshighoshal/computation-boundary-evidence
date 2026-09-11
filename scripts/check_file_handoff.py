"""Replay a preserved bundle into an offline repair image; no model or verifier calls."""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

from scicontext.io import digest_file, digest_json, read_json, write_json
from scicontext.pier_agent import ScientificCodex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--image", required=True, help="Pinned task environment image, already available locally")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve prior checks; choose a new output directory")
    if "@sha256:" not in args.image:
        raise ValueError("Use the pinned task environment image")
    args.output.mkdir(parents=True)
    original = read_json(args.bundle)

    def docker(*command):
        return subprocess.run(["docker", *command], check=True, text=True, capture_output=True, timeout=60).stdout.strip()

    class ExtractionReplay:
        async def download_dir(self, *args):
            pass  # The already preserved raw scratch is not recopied for this replay.
        async def download_file(self, source, target):
            shutil.copyfile(args.bundle, target)

    container = docker("create", "--network", "none", "--platform", "linux/amd64", "--entrypoint", "/bin/sh",
                       args.image, "-c", "sleep 300")
    try:
        docker("start", container)
        docker("exec", container, "mkdir", "-p", "/opt/scicontext/context")
        class Repair:
            async def upload_file(self, source, target):
                docker("cp", str(source), container + ":" + target)
        driver = SimpleNamespace(extract_environment=ExtractionReplay(), environment=Repair(),
            logs_dir=args.output, root="/app/task_" + original["graph"]["task_id"],
            task_id=original["graph"]["task_id"], _selected_remote="preserved-bundle.json")
        bundle = asyncio.run(ScientificCodex.collect_graph(driver, 60))
        code = (
            "import hashlib,json,pathlib; p=pathlib.Path('/opt/scicontext/context'); "
            "print(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in p.iterdir()}))")
        # This is a new repair container: none of the extraction scratch is present.
        guest_hashes = json.loads(docker("exec", container, "python", "-c", code))
        host_hashes = {name: digest_file(args.output / name) for name in bundle["handoff_files"]}
        assert guest_hashes == host_hashes
        graph = read_json(args.output / "scientific-graph.json")
        assert graph == original["graph"]
        assert digest_json(graph) == original["graph_sha256"]
        guide = (args.output / "scientific-guide.md").read_text()
        annotations = [obj for obj in graph["objects"] if obj.get("interpretation")]
        for obj in annotations:
            assert obj["id"] in guide
            value = obj["interpretation"]
            assert not value.get("meaning") or value["meaning"] in guide
            assert all(statement in guide for field in ("conventions", "assumptions") for statement in value.get(field, []))
        receipt = {"status": "passed", "model_calls": 0, "verifier_calls": 0,
            "input_bundle": str(args.bundle), "input_bundle_sha256": digest_file(args.bundle),
            "image": args.image, "network": "none", "graph_sha256": digest_json(graph),
            "objects": len(graph["objects"]), "annotations_preserved": len(annotations),
            "previous_inline_bytes": len(original["handoff"].encode()),
            "file_pointer_bytes": len(bundle["handoff"].encode()), "guide_bytes": len(guide.encode()),
            "guest_file_sha256": guest_hashes, "host_file_sha256": host_hashes}
        write_json(args.output / "receipt.json", receipt)
        print(json.dumps(receipt, indent=2))
    finally:
        # Only the new disposable replay container; all receipts/copies stay on the host.
        docker("rm", "-f", container)


if __name__ == "__main__":
    main()
