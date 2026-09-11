"""Pure-Python /proc observer: process tree, threads, memory, I/O patterns.

Runs as a thread alongside the traced workflow and samples /proc every 200 ms.
Language-agnostic: observes any process (compiled, interpreted, parallel) that
the workflow spawns. Produces observer.jsonl plus a deterministic
observer_summary.json.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

SAMPLE_INTERVAL = 0.2
RSS_SLOPE_TAIL = 0.5
HOT_THREAD_FRACTION = 0.2
STALL_CPU_RATE = 0.8
IDLE_CPU_RATE = 0.05


def _read(path: str) -> str | None:
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8", "replace")
    except (OSError, PermissionError):
        return None


def _descendants(root_pid: int) -> dict[int, int]:
    tree: dict[int, int] = {}
    for entry in Path("/proc").glob("[0-9]*"):
        stat = _read(f"/proc/{entry.name}/stat")
        if not stat:
            continue
        try:
            pid = int(entry.name)
        except ValueError:
            continue
        fields = stat.rsplit(")", 1)[1].split()
        if len(fields) < 3:
            continue
        tree[pid] = int(fields[1])
    return {pid: ppid for pid, ppid in tree.items() if ppid == root_pid
            or _ancestor(ppid, root_pid, tree)}


def _ancestor(pid: int, root: int, tree: dict[int, int]) -> bool:
    seen = set()
    while pid in tree and pid not in seen:
        if pid == root:
            return True
        seen.add(pid)
        pid = tree[pid]
    return False


class ProcObserver:
    def __init__(self, out: Path):
        self.out = out
        self.samples: list[dict] = []
        self.fd_positions: dict[tuple[int, str], list] = {}
        self.processes: dict[int, dict] = {}
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.started = time.monotonic()
        self.thread.start()

    def stop(self):
        self._stop.set()
        self.thread.join(timeout=5)
        (self.out / "observer.jsonl").write_text(
            "\n".join(json.dumps(s, ensure_ascii=False) for s in self.samples) + "\n")
        (self.out / "observer_summary.json").write_text(json.dumps(self.summary(), indent=2) + "\n")

    def _sample(self, tick: float) -> dict:
        root = os.getpid()
        descendants = _descendants(root)
        record = {"t": round(tick, 3), "processes": []}
        for pid in sorted({root, *descendants}):
            status = _read(f"/proc/{pid}/status") or ""
            fields = {}
            for line in status.splitlines():
                if line.startswith(("VmRSS:", "VmHWM:", "Threads:")):
                    key, _, value = line.partition(":")
                    fields[key.strip()] = int(value.strip().split()[0])
            io_bytes = {}
            for key in ("rchar", "wchar", "read_bytes", "write_bytes"):
                line = _read(f"/proc/{pid}/io")
                if line:
                    for part in line.splitlines():
                        if part.startswith(key + ":"):
                            io_bytes[key] = int(part.split(":")[1].strip())
            exe = os.readlink(f"/proc/{pid}/exe") if pid != root else "python"
            threads = []
            total_utime = total_stime = 0
            for tid_dir in Path(f"/proc/{pid}/task").glob("[0-9]*"):
                stat = _read(f"/proc/{tid_dir}/stat")
                if not stat:
                    continue
                try:
                    fields_stat = stat.rsplit(")", 1)[1].split()
                    comm = stat[stat.index("(") + 1:stat.index(")")]
                    utime, stime = int(fields_stat[11]), int(fields_stat[12])
                    total_utime += utime
                    total_stime += stime
                    threads.append({"tid": tid_dir.name, "comm": comm, "utime": utime, "stime": stime})
                except (ValueError, IndexError):
                    continue
            fds = []
            for fd in Path(f"/proc/{pid}/fd").glob("*"):
                target = os.readlink(fd)
                if not target.startswith("/") or target.startswith(("/proc", "/dev", "/sys")):
                    continue
                info = _read(f"/proc/{pid}/fdinfo/{fd.name}") or ""
                pos = None
                for line in info.splitlines():
                    if line.startswith("pos:"):
                        pos = int(line.split(":")[1].strip())
                if pos is not None:
                    key = (pid, target)
                    self.fd_positions.setdefault(key, []).append((tick, pos))
                fds.append({"path": target, "pos": pos})
            self.processes.setdefault(pid, {"exe": exe, "first_seen": round(tick, 3)})
            record["processes"].append({**self.processes[pid], "pid": pid,
                                       "vmrss_kb": fields.get("VmRSS"), "vmhwm_kb": fields.get("VmHWM"),
                                       "threads": len(threads), "utime": total_utime, "stime": total_stime,
                                       "io": io_bytes, "fds": fds})
        return record

    def _loop(self):
        while not self._stop.is_set():
            tick = time.monotonic() - self.started
            try:
                self.samples.append(self._sample(tick))
            except Exception:
                pass
            self._stop.wait(SAMPLE_INTERVAL)

    def summary(self) -> dict:
        by_pid: dict[int, dict] = {}
        for sample in self.samples:
            for process in sample["processes"]:
                entry = by_pid.setdefault(process["pid"], {"exe": process["exe"],
                                                           "max_rss_kb": 0, "threads_max": 0,
                                                           "cpu_seconds": 0.0, "threads": {},
                                                           "first_seen": process["first_seen"],
                                                           "last_seen": sample["t"]})
                entry["max_rss_kb"] = max(entry["max_rss_kb"], process.get("vmrss_kb") or 0)
                entry["threads_max"] = max(entry["threads_max"], process.get("threads") or 0)
                entry["last_seen"] = sample["t"]
                for thread in process.get("threads", []):
                    entry["threads"].setdefault(thread["tid"], {"comm": thread["comm"],
                                                                "utime": thread["utime"],
                                                                "stime": thread["stime"]})
        summary: dict = {"processes": []}
        for pid, entry in by_pid.items():
            cpu = sum(t["utime"] + t["stime"] for t in entry["threads"].values()) / 100.0
            wall = max(0.01, entry["last_seen"] - entry["first_seen"])
            thread_cpus = [(tid, (t["utime"] + t["stime"]) / 100.0) for tid, t in entry["threads"].items()]
            hot = [tid for tid, seconds in thread_cpus if seconds >= HOT_THREAD_FRACTION * cpu] if cpu else []
            summary["processes"].append({"pid": pid, "exe": entry["exe"],
                                         "wall_seconds": round(wall, 2), "cpu_seconds": round(cpu, 2),
                                         "cpu_rate": round(cpu / wall, 2), "max_rss_kb": entry["max_rss_kb"],
                                         "threads_max": entry["threads_max"], "hot_threads": hot})
        files = []
        for (pid, path), series in sorted(self.fd_positions.items()):
            positions = [pos for _, pos in series]
            if len(positions) < 2:
                continue
            deltas = [b - a for a, b in zip(positions, positions[1:])]
            forward = sum(1 for d in deltas if d > 0) / len(deltas)
            backward = sum(1 for d in deltas if d < 0) / len(deltas)
            pattern = "sequential" if forward >= 0.9 else "random" if backward >= 0.25 else "mixed"
            files.append({"pid": pid, "path": path, "io_pattern": pattern,
                          "bytes_moved": positions[-1] - positions[0],
                          "final_pos": positions[-1]})
        summary["files"] = files
        summary["stall"] = self._stall(summary)
        return summary

    def _stall(self, summary: dict) -> dict | None:
        if not self.samples or len(self.samples) < 5:
            return None
        last = self.samples[-1]
        processes = last.get("processes") or []
        if not processes:
            return None
        total_cpu_rate = sum(p.get("utime", 0) + p.get("stime", 0) for p in processes) / 100.0
        window = max(0.2, last["t"] - self.samples[max(0, len(self.samples) - 5)]["t"])
        rate = total_cpu_rate / window if window else 0.0
        if rate >= STALL_CPU_RATE:
            return {"kind": "compute_stall", "cpu_rate": round(rate, 2)}
        if rate < IDLE_CPU_RATE:
            return {"kind": "idle_hang", "cpu_rate": round(rate, 2)}
        return None
