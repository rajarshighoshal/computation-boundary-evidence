"""Workflow tracer: observe the public reproduce script inside the task image.

Records one JSON line per completed repository-function call with argument and
return fingerprints, plus script-module observables and script-declared
predicates evaluated on the script frame. Uses CPython 3.12 sys.monitoring
(PEP 669); falls back to sys.setprofile. Native (C-level) calls are not
profiled; the /proc observer covers processes that leave Python.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import json
import os
import runpy
import sys
import threading
import time
from pathlib import Path

TRACER_VERSION = "trace_runtime-1.0"
MAX_INSTANCES_PER_FUNC = 64
MAX_VALUE_BYTES = 16 * 1024 * 1024
MAX_CONTAINER_ITEMS = 1000


def _parse_predicates(script_text: str) -> list:
    """Script-declared comparison predicates of the forms X==Y, X!=Y,
    np.allclose(X,Y), (X>=a).all(), (X<b).all(), abs(X-Y)<tol, X[i]==Y[j]."""
    tree = ast.parse(script_text)
    forms = []
    for node in ast.walk(tree):
        test = None
        if isinstance(node, ast.Assert):
            test = node.test
        elif isinstance(node, ast.Raise) and node.exc is not None:
            test = node.exc
        elif isinstance(node, ast.If) and isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not):
            test = node.test.operand
        if test is None:
            continue
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            test = test.operand
        kind = None
        if isinstance(test, ast.Compare):
            kind = "equality" if isinstance(test.ops[0], ast.Eq) else (
                "inequality" if isinstance(test.ops[0], ast.NotEq) else "bounds")
        elif isinstance(test, ast.Call):
            name = _call_name(test.func)
            if name in {"all", "any", "np.all", "np.any", "numpy.all", "numpy.any"} or name.endswith((".all", ".any")):
                kind = "bounds"
            elif "allclose" in name:
                kind = "closeness"
        if kind and getattr(node, "lineno", None):
            forms.append({"kind": kind, "line": node.lineno,
                          "operands": [ast.unparse(o) for o in _operands(test)],
                          "text": ast.unparse(test)})
    return forms


def _call_name(node) -> str:
    if isinstance(node, ast.Attribute):
        return f"{_call_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _operands(node) -> list:
    if isinstance(node, ast.Compare):
        return [node.left, *node.comparators]
    if isinstance(node, ast.Call):
        return node.args
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
        return [node.left, node.right]
    return [node]


def _root_name(expression: str) -> str | None:
    tree = ast.parse(expression, mode="eval")
    node = tree.body
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value if isinstance(node, ast.Attribute) else node.value
    if isinstance(node, ast.Name):
        return node.id
    return None


class _Tracer:
    def __init__(self, root: Path, script: Path, out: Path, observe: bool):
        self.root = root.resolve()
        self.script = script.resolve()
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.observe = observe
        self.stacks: dict[int, list] = {}
        self.seq = 0
        self.func_counts: dict = {}
        self.in_fingerprint = False
        self.in_callback = False
        self.records = []
        self.script_frame_global_ids: set[int] = set()
        self.predicates = _parse_predicates(script.read_text())
        self.predicate_evaluations = []
        self.started = time.monotonic()
        self.trace_file = gzip.open(out / "trace.jsonl.gz", "wt", encoding="utf-8")
        from .fingerprint import fingerprint
        self.fingerprint = fingerprint
        if observe:
            from .proc_observer import ProcObserver
            self.observer = ProcObserver(out)
        else:
            self.observer = None

    def _eligible(self, frame) -> bool:
        filename = frame.f_code.co_filename
        if not filename.startswith(str(self.root)):
            return False
        if "site-packages" in filename or "/.venv/" in filename:
            return False
        return True

    def on_start_entry(self, code, offset, legacy_frame=None):
        # PY_START: the started function's frame is guaranteed on the stack.
        if self.in_callback:
            return
        self.in_callback = True
        try:
            frame = legacy_frame if legacy_frame is not None else sys._getframe(1)
            if frame is None or not self._eligible(frame):
                return
            thread_stacks = self.stacks.setdefault(threading.get_ident(), [])
            parent = thread_stacks[-1]["seq"] if thread_stacks else None
            self.seq += 1
            func_key = (frame.f_code.co_filename, frame.f_code.co_qualname, frame.f_code.co_firstlineno)
            count = self.func_counts.get(func_key, 0)
            self.func_counts[func_key] = count + 1
            record = {"seq": self.seq, "name": frame.f_code.co_qualname,
                      "file": os.path.relpath(frame.f_code.co_filename, self.root),
                      "line": frame.f_code.co_firstlineno, "parent_seq": parent,
                      "pid": os.getpid(), "tid": threading.get_ident(),
                      "t0": time.monotonic() - self.started,
                      "fingerprinted": count < MAX_INSTANCES_PER_FUNC}
            if record["fingerprinted"] and not os.environ.get("SCITRACE_SKIP_INPUTS"):
                self._record_inputs(frame, record)
            thread_stacks.append(record)
        finally:
            self.in_callback = False

    def _guarded_fingerprint(self, value):
        try:
            size = sys.getsizeof(value)
        except TypeError:
            size = 0
        if size > MAX_VALUE_BYTES or (isinstance(value, (dict, list, tuple, set, frozenset))
                                      and len(value) > MAX_CONTAINER_ITEMS) or not self._safe_to_recurse(value):
            return {"t": "opaque", "exact": None, "equiv": None, "multiset": None,
                    "rev": None, "struct": type(value).__name__, "bytes": size, "truncated": True}
        return self.fingerprint(value)

    def _log_return_size(self, record, value):
        try:
            module = type(value).__module__
            size = sys.getsizeof(value)
            deep = ""
            if hasattr(value, "memory_usage"):
                try:
                    deep = f" mem={int(value.memory_usage(index=True, deep=False).sum())}"
                except Exception:
                    pass
            if hasattr(value, "nbytes") and not hasattr(value, "memory_usage"):
                deep = f" nbytes={getattr(value, 'nbytes')}"
            with open(self.out / "return_sizes.log", "a") as handle:
                handle.write(f"{record['seq']} {record['name']} {module}.{type(value).__name__} {size}{deep}\n")
                handle.flush()
        except Exception:
            pass

    @staticmethod
    def _safe_to_recurse(value):
        """Only builtin/numpy types and plain containers of them are fingerprinted;
        third-party object internals are opaque (prevents C-extension crashes)."""
        root = (type(value).__module__ or "").split(".")[0]
        if root in {"builtins", "numpy", "pandas"}:
            return True
        if isinstance(value, dict):
            return all(_Tracer._safe_to_recurse(k) and _Tracer._safe_to_recurse(v)
                       for k, v in list(value.items())[:MAX_CONTAINER_ITEMS])
        if isinstance(value, (list, tuple, set, frozenset)):
            return all(_Tracer._safe_to_recurse(item) for item in list(value)[:MAX_CONTAINER_ITEMS])
        return False

    def _record_inputs(self, frame, record):
        code = frame.f_code
        names = list(code.co_varnames[: code.co_argcount + code.co_kwonlyargcount])
        inputs = {}
        self.in_fingerprint = True
        try:
            for name in names:
                value = frame.f_locals.get(name)
                if value is not None:
                    inputs[name] = self._guarded_fingerprint(value)
            if names and names[0] in {"self", "cls"}:
                value = frame.f_locals.get(names[0])
                state = getattr(value, "__dict__", None)
                if state is not None and len(state) <= 50 and sys.getsizeof(state) <= MAX_VALUE_BYTES:
                    inputs["self.__dict__"] = self._guarded_fingerprint(state)
        finally:
            self.in_fingerprint = False
        record["inputs"] = inputs

    def on_return(self, code, offset, retval):
        if self.in_callback:
            return
        self.in_callback = True
        try:
            self._on_return(code, offset, retval)
        finally:
            self.in_callback = False

    def _on_return(self, code, offset, retval):
        thread_stacks = self.stacks.get(threading.get_ident())
        if not thread_stacks:
            return
        record = thread_stacks.pop()
        record["duration"] = time.monotonic() - self.started - record.pop("t0")
        record.pop("count", None)
        if record.get("fingerprinted") and not os.environ.get("SCITRACE_SKIP_RETURNS"):
            if os.environ.get("SCITRACE_DEBUG_RETURNS"):
                self._log_return_size(record, retval)
            self.in_fingerprint = True
            try:
                record["return_fp"] = self._guarded_fingerprint(retval)
            finally:
                self.in_fingerprint = False
        else:
            record["return_fp"] = None
        record["fingerprinted"] = record.get("fingerprinted", False)
        self.trace_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def on_raise(self, code, offset, exception):
        if self.in_callback:
            return
        self.in_callback = True
        try:
            self._on_raise(code, offset, exception)
        finally:
            self.in_callback = False

    def _on_raise(self, code, offset, exception):
        thread_stacks = self.stacks.get(threading.get_ident())
        if not thread_stacks:
            return
        record = thread_stacks.pop()
        record["exception"] = f"{type(exception).__name__}: {exception}"
        record["duration"] = time.monotonic() - self.started - record.pop("t0")
        self.trace_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def _evaluate_predicates(self, globals_dict):
        for predicate in self.predicates:
            values = {}
            for operand in predicate["operands"]:
                name = _root_name(operand)
                if name is None:
                    continue
                value = globals_dict.get(name)
                if value is not None:
                    self.in_fingerprint = True
                    try:
                        values[name] = self.fingerprint(value)
                    finally:
                        self.in_fingerprint = False
            if values:
                self.predicate_evaluations.append({**predicate, "evaluated": values})

    def _capture_script_globals(self, globals_dict):
        if id(globals_dict) in self.script_frame_global_ids:
            return
        self.script_frame_global_ids.add(id(globals_dict))
        self._evaluate_predicates(globals_dict)
        observables = []
        for name, value in globals_dict.items():
            if name.startswith("__") or callable(value):
                continue
            self.in_fingerprint = True
            try:
                if type(value).__name__ in {"ndarray", "Series", "DataFrame"} or isinstance(value, (list, dict, float)):
                    observables.append({"name": name, "fp": self.fingerprint(value)})
            finally:
                self.in_fingerprint = False
        (self.out / "script_observables.json").write_text(json.dumps(observables, indent=2, default=str) + "\n")

    def run(self, seconds: float):
        self.deadline = self.started + seconds
        if self.observer:
            self.observer.start()
        script_error = None
        try:
            use_monitoring = hasattr(sys, "monitoring")
            if use_monitoring:
                events = sys.monitoring.events
                event_return = events.PY_RETURN
                event_raise = getattr(events, "PY_RAISE", getattr(events, "RAISE", events.PY_THROW))
                event_start = events.PY_START
                sys.monitoring.use_tool_id(0, "scitrace")
                sys.monitoring.set_events(0, event_return | event_raise | event_start)
                sys.monitoring.register_callback(0, event_return, self.on_return)
                sys.monitoring.register_callback(0, event_raise, self.on_raise)
                sys.monitoring.register_callback(0, event_start, self.on_start_entry)
                try:
                    self._run_script()
                finally:
                    for event in (event_return, event_raise, event_start):
                        sys.monitoring.register_callback(0, event, None)
                    sys.monitoring.free_tool_id(0)
            else:
                sys.setprofile(self._legacy_hook)
                try:
                    self._run_script()
                finally:
                    sys.setprofile(None)
        except SystemExit:
            pass
        except Exception as error:
            script_error = f"{type(error).__name__}: {error}"
        finally:
            outputs_dir = self.script.parent / "outputs"
            if outputs_dir.is_dir():
                candidates = [candidate for candidate in outputs_dir.glob("*.json")
                              if candidate.stat().st_mtime >= self.started - 1]
                if candidates:
                    newest = max(candidates, key=lambda c: c.stat().st_mtime)
                    try:
                        import shutil
                        shutil.copyfile(newest, self.out / "script_report.json")
                    except OSError:
                        pass
            if not (self.out / "script_report.json").exists():
                captured = getattr(self, "_captured_stdout", "") or ""
                try:
                    start = captured.rindex("{")
                    end = captured.rindex("}")
                    if end > start:
                        blob = json.loads(captured[start:end + 1])
                        if isinstance(blob, dict) and "status" in blob:
                            (self.out / "script_report.json").write_text(
                                json.dumps(blob, indent=2) + "\n")
                except (ValueError, json.JSONDecodeError):
                    pass
            self.trace_file.close()
            (self.out / "script_predicates.json").write_text(
                json.dumps({"declared": self.predicates, "evaluations": self.predicate_evaluations},
                           indent=2, default=str) + "\n")
            if self.observer:
                self.observer.stop()
            run = {"status": "completed", "script_status": script_error,
                   "wall_seconds": round(time.monotonic() - self.started, 3),
                   "instances": self.seq, "func_keys": len(self.func_counts),
                   "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
                   "tracer_version": TRACER_VERSION, "seconds_bound": seconds,
                   "capped_funcs": {":".join(map(str, k)): v for k, v in self.func_counts.items()
                                    if v > MAX_INSTANCES_PER_FUNC}}
            (self.out / "run.json").write_text(json.dumps(run, indent=2) + "\n")

    def _run_script(self):
        import contextlib
        import io
        sys.argv = [str(self.script)]
        previous = os.getcwd()
        os.chdir(self.script.parent)
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                globals_dict = runpy.run_path(str(self.script), run_name="__main__")
            self._capture_script_globals(globals_dict)
        finally:
            os.chdir(previous)
            self._captured_stdout = buffer.getvalue()

    def _legacy_hook(self, frame, event, arg):
        try:
            if event == "call":
                self.on_start_entry(None, None, legacy_frame=frame)
                return self._legacy_hook
            if event == "return":
                self.on_return(None, None, arg)
            elif event == "exception":
                self.on_raise(None, None, arg[1])
        except Exception as error:
            with open(self.out / "hook_errors.jsonl", "a") as handle:
                handle.write(json.dumps({"event": event, "error": f"{type(error).__name__}: {error}",
                                         "frame": frame.f_code.co_filename if frame else None}) + "\n")
        return self._legacy_hook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--observe", action="store_true")
    args = parser.parse_args(argv)
    tracer = _Tracer(args.root.resolve(), args.script.resolve(), args.out.resolve(), args.observe)
    tracer.run(args.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
