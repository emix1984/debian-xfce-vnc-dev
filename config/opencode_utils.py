"""
Shared utilities for OpenCode setup scripts (plugins, skills, etc.)
"""
import os
import shutil
import time
import subprocess
from pathlib import Path
from typing import Optional

# =====================================
# OpenCode Path Setup
# =====================================
ACTUAL_HOME = Path(os.getenv("ACTUAL_HOME", "/headless"))
OPENCODE_HOME = Path(os.getenv("OPENCODE_HOME", str(ACTUAL_HOME / ".opencode")))
OPENCODE_CONFIG_DIR = Path(os.getenv("OPENCODE_CONFIG_DIR", str(ACTUAL_HOME / ".config" / "opencode")))
OPENCODE_CONFIG_FILE = OPENCODE_CONFIG_DIR / "opencode.jsonc"

# Update PATH
os.environ["PATH"] = f"{OPENCODE_HOME}/bin:{os.environ.get('PATH', '')}"

# Log Directory
LOG_DIR = Path(os.getenv("LOG_DIR", "/dockerstartup/custom"))
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    LOG_DIR = Path("/tmp/opencode-mcp")
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_log_file(script_name: str) -> Path:
    return LOG_DIR / f"{script_name}.log"

def log(msg: str, level: str = "INFO", log_file: Optional[Path] = None) -> None:
    """Log to stdout and append to the specified log file."""
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    print(line)
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

def command_exists(cmd: str) -> bool:
    """Check if command exists in PATH"""
    return shutil.which(cmd) is not None

def find_bun() -> Optional[str]:
    """Find the path to the bun executable."""
    for p in [
        os.path.join(ACTUAL_HOME, ".bun", "bin", "bun"),
        os.path.join(os.environ.get("HOME", "/root"), ".bun", "bin", "bun"),
        "/usr/local/bin/bun",
        "/usr/bin/bun",
    ]:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which("bun")

def find_bunx() -> Optional[str]:
    """Find the path to the bunx executable."""
    for p in [
        os.path.join(ACTUAL_HOME, ".bun", "bin", "bunx"),
        os.path.join(os.environ.get("HOME", "/root"), ".bun", "bin", "bunx"),
        "/usr/local/bin/bunx",
        "/usr/bin/bunx",
    ]:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which("bunx")

def ensure_bunx(log_file: Optional[Path] = None) -> str:
    """Find bunx or install it if missing."""
    bunx_path = find_bunx()
    if bunx_path:
        return bunx_path

    log("bunx not found, attempting to install bun@latest...", "INFO", log_file)
    try:
        result = subprocess.run(
            ["npm", "install", "-g", "bun"],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            log(f"npm install failed: {result.stderr[:500]}", "ERROR", log_file)
            raise RuntimeError("Failed to install bun via npm")
    except FileNotFoundError:
        log("npm not found in PATH. Install Node.js/npm or set BUNX env var.", "ERROR", log_file)
        raise RuntimeError("npm not found: please install Node.js and npm")
    except Exception as e:
        log(f"ERROR running npm install: {e}", "ERROR", log_file)
        raise RuntimeError("Failed to run npm to install bun") from e

    bunx_path = find_bunx()
    if not bunx_path:
        raise RuntimeError("bunx still not found after npm install")

    log(f"Successfully installed bun, bunx at: {bunx_path}", "INFO", log_file)
    return bunx_path

def restart_webui(port: int = 4096, log_file: Optional[Path] = None) -> None:
    """Restart OpenCode WebUI"""
    restart_script = Path(__file__).resolve().parent / "restart_opencode.sh"
    if restart_script.exists():
        log(f"Restarting WebUI via {restart_script}...", "INFO", log_file)
        result = subprocess.run(
            ["bash", str(restart_script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log(f"Restart script failed: {result.stderr[:500]}", "WARN", log_file)
        else:
            log("Restart script completed successfully", "INFO", log_file)
    else:
        log(f"{restart_script} not found, restarting directly...", "INFO", log_file)
        # Kill existing processes
        subprocess.run(["pkill", "-f", "opencode web"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        subprocess.run(["pkill", "-9", "-f", "opencode web"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

        try:
            result = subprocess.run(["which", "opencode"], capture_output=True, text=True)
            bin_path = result.stdout.strip() or "opencode"
        except Exception:
            bin_path = "opencode"

        webui_log = LOG_DIR / "opencode_web.log"
        subprocess.Popen(
            f"nohup {bin_path} web --hostname 0.0.0.0 --port {port} >> {webui_log} 2>&1 &",
            shell=True,
        )
        log("[OK] WebUI launched directly", "INFO", log_file)
