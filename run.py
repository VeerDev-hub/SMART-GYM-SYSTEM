"""
run.py -- Smart Gym IoT System Launcher
Starts all software services required for the Smart Gym system:
  1. FastAPI Backend (uvicorn)
  2. Dashboard static file server
  3. AI Vision Engine (optional, requires camera)
  4. mDNS Advertiser (smartgym.local)

Usage:
    python run.py                  # Start backend + dashboard
    python run.py --with-vision    # Start backend + dashboard + AI vision
    python run.py --backend-only   # Start backend only
"""

import argparse
import http.server
import os
import subprocess
import sys
import threading
import time
import socket
from zeroconf import IPVersion, ServiceInfo, Zeroconf

# -- Paths --
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
DASHBOARD_DIR = os.path.join(ROOT_DIR, "Smart-Gym", "web-dashboard")
AI_VISION_DIR = os.path.join(ROOT_DIR, "Smart-Gym", "ai-vision")

# -- Defaults --
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8080
DASHBOARD_PORT = 3000

processes = []
stop_event = threading.Event()
zeroconf = None


def sync_ip_to_configs(ip):
    """Automatically update config files with the current local IP."""
    log("LAUNCHER", f"Syncing IP {ip} to configuration files...")
    
    # Update firmware-machine config.h
    machine_config = os.path.join(ROOT_DIR, "firmware-machine", "include", "config.h")
    if os.path.exists(machine_config):
        with open(machine_config, "r") as f:
            lines = f.readlines()
        with open(machine_config, "w") as f:
            for line in lines:
                if line.startswith("#define BACKEND_URL"):
                    f.write(f'#define BACKEND_URL "http://{ip}:8080"\n')
                else:
                    f.write(line)
        log("LAUNCHER", f"Updated {os.path.basename(machine_config)} with IP {ip}")

    # Update firmware-entrance config.h
    entrance_config = os.path.join(ROOT_DIR, "firmware-entrance", "include", "config.h")
    if os.path.exists(entrance_config):
        with open(entrance_config, "r") as f:
            lines = f.readlines()
        with open(entrance_config, "w") as f:
            for line in lines:
                if line.startswith("#define BACKEND_URL"):
                    f.write(f'#define BACKEND_URL "http://{ip}:8080"\n')
                else:
                    f.write(line)
        log("LAUNCHER", f"Updated {os.path.basename(entrance_config)} with IP {ip}")


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def start_mdns(port):
    """Advertise the backend as smartgym.local on the network."""
    global zeroconf
    desc = {'path': '/'}
    local_ip = get_ip()
    
    info = ServiceInfo(
        "_http._tcp.local.",
        "SmartGym._http._tcp.local.",
        addresses=[socket.inet_aton(local_ip)],
        port=port,
        properties=desc,
        server="smartgym.local.",
    )
    
    zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
    log("LAUNCHER", f"Advertising as smartgym.local (IP: {local_ip})")
    zeroconf.register_service(info)


def log(tag, message):
    colors = {
        "LAUNCHER": "\033[96m",
        "BACKEND": "\033[92m",
        "DASHBOARD": "\033[95m",
        "VISION": "\033[93m",
        "ERROR": "\033[91m",
    }
    reset = "\033[0m"
    color = colors.get(tag, "")
    print(f"{color}[{tag}]{reset} {message}")


def ensure_dependencies():
    """Check if uvicorn is importable; if not, install backend requirements."""
    try:
        import uvicorn  # noqa: F401
        return True
    except ImportError:
        pass

    req_file = os.path.join(BACKEND_DIR, "requirements.txt")
    if not os.path.exists(req_file):
        log("ERROR", "uvicorn not found and no requirements.txt to install from.")
        return False

    log("LAUNCHER", "uvicorn not found -- installing backend dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file, "-q"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log("ERROR", f"pip install failed:\n{result.stderr}")
        return False

    log("LAUNCHER", "Dependencies installed successfully.")
    return True


def stream_output(proc, tag):
    """Stream subprocess stdout line by line."""
    try:
        for line in iter(proc.stdout.readline, b""):
            if stop_event.is_set():
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                log(tag, text)
    except Exception:
        pass


def start_backend(port):
    """Start the FastAPI backend with uvicorn."""
    log("LAUNCHER", f"Starting FastAPI backend on http://{BACKEND_HOST}:{port}")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",  # Listen on all interfaces
            "--port", str(port),
            "--reload",
        ],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append(proc)
    thread = threading.Thread(target=stream_output, args=(proc, "BACKEND"), daemon=True)
    thread.start()
    return proc


def start_dashboard_server(port):
    """Start a simple HTTP server for the dashboard static files."""
    log("LAUNCHER", f"Starting Dashboard server on http://{BACKEND_HOST}:{port}")

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("0.0.0.0", port), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log("DASHBOARD", f"Dashboard is live at http://{BACKEND_HOST}:{port}")
    return server


def start_ai_vision():
    """Start the AI Vision engine (requires a camera)."""
    vision_main = os.path.join(AI_VISION_DIR, "main.py")
    if not os.path.exists(vision_main):
        log("ERROR", f"AI Vision script not found at {vision_main}")
        return None

    log("LAUNCHER", "Starting AI Vision Engine (camera required)...")
    proc = subprocess.Popen(
        [sys.executable, vision_main],
        cwd=AI_VISION_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    processes.append(proc)
    thread = threading.Thread(target=stream_output, args=(proc, "VISION"), daemon=True)
    thread.start()
    return proc


def shutdown():
    """Gracefully terminate all child processes."""
    global zeroconf
    if stop_event.is_set():
        return
    stop_event.set()
    
    if zeroconf:
        log("LAUNCHER", "Stopping mDNS...")
        zeroconf.close()
        
    log("LAUNCHER", "Shutting down all services...")
    for proc in processes:
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    log("LAUNCHER", "All services stopped. Goodbye!")


def main():
    parser = argparse.ArgumentParser(description="Smart Gym IoT System Launcher")
    parser.add_argument("--with-vision", action="store_true", help="Also start the AI Vision engine (requires camera)")
    parser.add_argument("--backend-only", action="store_true", help="Start only the FastAPI backend")
    parser.add_argument("--port", type=int, default=BACKEND_PORT, help="Backend port (default: 8080)")
    parser.add_argument("--dashboard-port", type=int, default=DASHBOARD_PORT, help="Dashboard port (default: 3000)")
    args = parser.parse_args()

    be_port = args.port
    dash_port = args.dashboard_port

    print()
    log("LAUNCHER", "================================================")
    log("LAUNCHER", "       Smart Gym IoT System -- Starting Up      ")
    log("LAUNCHER", "================================================")
    print()

    # 0. Ensure dependencies are installed
    if not ensure_dependencies():
        log("ERROR", "Cannot start without backend dependencies. Exiting.")
        return

    # 1. Sync IP to configs
    current_ip = get_ip()
    sync_ip_to_configs(current_ip)

    # 2. Start mDNS
    try:
        start_mdns(be_port)
    except Exception as e:
        log("ERROR", f"Failed to start mDNS: {e}")

    # 2. Backend
    backend_proc = start_backend(be_port)
    time.sleep(3)  # Let backend spin up

    if backend_proc.poll() is not None:
        log("ERROR", "Backend failed to start!")
    else:
        log("BACKEND", "Backend process started successfully.")

    # 3. Dashboard
    if not args.backend_only:
        start_dashboard_server(dash_port)

    # 4. AI Vision (optional)
    if args.with_vision:
        start_ai_vision()

    print()
    log("LAUNCHER", "----------------------------------------------")
    log("LAUNCHER", f"  Local IP    : {get_ip()}")
    log("LAUNCHER", f"  mDNS Host   : http://smartgym.local:{be_port}")
    log("LAUNCHER", f"  Dashboard   : http://localhost:{dash_port}")
    log("LAUNCHER", "----------------------------------------------")
    log("LAUNCHER", "  Press Ctrl+C to stop all services.")
    print()

    try:
        while not stop_event.is_set():
            if backend_proc.poll() is not None and not stop_event.is_set():
                log("ERROR", "Backend process died. Restarting in 3 seconds...")
                time.sleep(3)
                if not stop_event.is_set():
                    processes.remove(backend_proc)
                    backend_proc = start_backend(be_port)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        shutdown()


if __name__ == "__main__":
    main()
