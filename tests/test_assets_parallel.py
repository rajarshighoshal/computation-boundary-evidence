"""Cache creation is serialized between independent local processes."""
import multiprocessing
import subprocess
import time
import zipfile
from pathlib import Path

from scicontext import assets
from scicontext.io import read_json


def _prepare(cache, result):
    try:
        result.put(str(assets.prepare_helpers(cache, python_minor="311")))
    except BaseException as error:
        result.put(f"ERROR: {error}")


def test_two_processes_build_helper_cache_once(tmp_path, monkeypatch):
    calls = tmp_path / "downloads.txt"
    def download(command, **kwargs):
        with calls.open("a") as stream:
            stream.write("download\n")
        time.sleep(0.1)
        wheels = Path(command[command.index("--dest") + 1])
        with zipfile.ZipFile(wheels / "synthetic.whl", "w") as archive:
            archive.writestr("synthetic/__init__.py", "VERSION = 'synthetic'\n")
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(assets.subprocess, "run", download)
    # Fork inherits only this fake downloader. No network, Docker or model calls.
    context = multiprocessing.get_context("fork")
    result = context.Queue()
    processes = [context.Process(target=_prepare, args=(tmp_path / "cache", result)) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        paths = [result.get(timeout=5) for _ in processes]
        for process in processes:
            process.join(timeout=5)
            assert process.exitcode == 0
        assert paths[0] == paths[1] and not paths[0].startswith("ERROR")
        assert calls.read_text() == "download\n"
        receipt = read_json(Path(paths[0]) / "receipt.json")
        assert "synthetic/__init__.py" in receipt["files"]
        assert assets.prepare_helpers(tmp_path / "cache", "311") == Path(paths[0])
        assert calls.read_text() == "download\n"
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        result.close()
