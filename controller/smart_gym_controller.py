from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent
CONTROLLER_DIR = Path(__file__).resolve().parent
PID_FILE = CONTROLLER_DIR / ".smart-gym-pids.json"
BACKEND_DB = ROOT / "backend" / "gym_iot.db"
LOG_DIR = CONTROLLER_DIR / "logs"
BACKEND_VENV_PYTHON = ROOT / "backend" / "venv" / "Scripts" / "python.exe"


def get_python_executable() -> str:
    return sys.executable


def get_backend_python_executable(default_python: str) -> str:
    if BACKEND_VENV_PYTHON.exists():
        return str(BACKEND_VENV_PYTHON)
    return default_python


def build_processes(python_exe: str) -> list[dict]:
    backend_python = get_backend_python_executable(python_exe)
    return [
        {
            "name": "backend",
            "cwd": ROOT / "backend",
            "cmd": [backend_python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        },
        {
            "name": "simulator",
            "cwd": ROOT / "Smart-Gym" / "demo-simulator",
            "cmd": [python_exe, "simulator.py"],
        },
        {
            "name": "ai-vision",
            "cwd": ROOT / "Smart-Gym" / "ai-vision",
            "cmd": [python_exe, "main.py"],
        },
        {
            "name": "dashboard",
            "cwd": ROOT / "Smart-Gym" / "web-dashboard",
            "cmd": [python_exe, "-m", "http.server", "8080"],
        },
    ]


def start_process(spec: dict) -> tuple[subprocess.Popen, Path]:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{spec['name']}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    kwargs = {
        "cwd": str(spec["cwd"]),
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "stdin": None,
    }

    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kwargs["start_new_session"] = True

    process = subprocess.Popen(spec["cmd"], **kwargs)
    return process, log_path


def write_pid_file(records: list[dict]) -> None:
    PID_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")


def read_pid_file() -> list[dict]:
    if not PID_FILE.exists():
        return []
    return json.loads(PID_FILE.read_text(encoding="utf-8"))


def process_is_alive(pid: int) -> bool:
    try:
        if os.name == "nt":
            output = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                check=False,
                capture_output=True,
                text=True,
            )
            return str(pid) in output.stdout

        os.kill(pid, 0)
        return True
    except OSError:
        return False


def terminate_pid(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
    else:
        os.kill(pid, signal.SIGTERM)


def ensure_paths_exist(processes: list[dict]) -> None:
    missing = [str(spec["cwd"]) for spec in processes if not spec["cwd"].exists()]
    if missing:
        raise FileNotFoundError("Missing required folders:\n" + "\n".join(missing))


def wait_for_backend(timeout_seconds: float = 10.0) -> bool:
    started = time.time()
    while time.time() - started < timeout_seconds:
        try:
            with urlopen("http://127.0.0.1:8000/", timeout=1.0) as response:
                return response.status == 200
        except Exception:
            time.sleep(0.4)
    return False


def command_start(recreate_db: bool) -> int:
    python_exe = get_python_executable()
    processes = build_processes(python_exe)
    ensure_paths_exist(processes)

    if recreate_db and BACKEND_DB.exists():
        BACKEND_DB.unlink()
        print(f"Deleted existing database: {BACKEND_DB}")

    launched: list[dict] = []
    try:
        for spec in processes:
            proc, log_path = start_process(spec)
            launched.append(
                {
                    "name": spec["name"],
                    "pid": proc.pid,
                    "cwd": str(spec["cwd"]),
                    "cmd": spec["cmd"],
                    "log": str(log_path),
                }
            )
            print(f"Started {spec['name']} (PID {proc.pid}) -> {log_path}")
            time.sleep(0.6)
    except Exception:
        for item in launched:
            terminate_pid(item["pid"])
        raise

    write_pid_file(launched)
    backend_ok = wait_for_backend()
    print("")
    print("Smart Gym controller started.")
    print("Backend:   http://127.0.0.1:8000")
    print("Dashboard: http://localhost:8080")
    if not backend_ok:
        print("Warning: backend did not become healthy.")
        print(f"Check backend log: {LOG_DIR / 'backend.log'}")
    print("Use `python controller/smart_gym_controller.py stop` to stop everything.")
    return 0


def command_stop() -> int:
    records = read_pid_file()
    if not records:
        print("No controller PID file found. Nothing to stop.")
        return 0

    for item in records:
        pid = item["pid"]
        if process_is_alive(pid):
            terminate_pid(pid)
            print(f"Stopped {item['name']} (PID {pid})")
        else:
            print(f"Process already stopped for {item['name']} (PID {pid})")

    if PID_FILE.exists():
        PID_FILE.unlink()
    print("Smart Gym controller shutdown complete.")
    return 0


def command_status() -> int:
    records = read_pid_file()
    if not records:
        print("No controller PID file found.")
        return 0

    for item in records:
        state = "running" if process_is_alive(item["pid"]) else "stopped"
        print(f"{item['name']}: PID {item['pid']} [{state}]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smart Gym unified controller")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Start backend, simulator, AI vision, and dashboard")
    start_parser.add_argument("--recreate-db", action="store_true", help="Delete backend/gym_iot.db before startup")

    subparsers.add_parser("stop", help="Stop every process launched by this controller")
    subparsers.add_parser("status", help="Show status of tracked processes")

    args = parser.parse_args()

    if args.command == "start":
        return command_start(args.recreate_db)
    if args.command == "stop":
        return command_stop()
    if args.command == "status":
        return command_status()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
