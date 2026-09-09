"""No-model probe executed through native Codex sandbox before authentication."""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
from pathlib import Path


def main() -> int:
    mode, root, scratch, control = sys.argv[1:]
    marker = Path(root) / ".scicontext-permission-probe"
    metadata = marker.stat()
    diagnostics = {"uid": os.getuid(), "marker_uid": metadata.st_uid,
                   "marker_mode": oct(metadata.st_mode), "source_write_errno": None}
    checks = {"source_read": marker.read_text() == "probe"}
    try:
        marker.write_text("write")
        checks["source_write_policy"] = mode == "repair"
    except OSError as error:
        diagnostics["source_write_errno"] = error.errno
        checks["source_write_policy"] = mode == "extract" and error.errno in (1, 13, 30)
    (Path(scratch) / "permission-probe").write_text("scratch")
    checks["scratch_write"] = True
    with tempfile.TemporaryDirectory() as temporary:
        checks["temporary_directory"] = Path(temporary).is_relative_to(Path(scratch))
    try:
        (Path(control) / "dummy-secret").read_text()
        checks["credential_read_denied"] = False
    except OSError as error:
        checks["credential_read_denied"] = error.errno in (1, 13)
    try:
        with socket.socket() as connection:
            connection.settimeout(0.1)
            connection.connect(("127.0.0.1", 9))
        checks["network_denied"] = False
    except OSError as error:
        # Refused/timed-out alone is not evidence of sandbox enforcement.
        checks["network_denied"] = error.errno in (1, 13)
    print(json.dumps({"profile": mode, "checks": checks, "diagnostics": diagnostics}, sort_keys=True))
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
