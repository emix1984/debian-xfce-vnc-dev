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


def find_agent_browser() -> Optional[str]:
    """Find the path to the agent-browser executable."""
    for p in [
        os.path.join(ACTUAL_HOME, ".npm-global", "bin", "agent-browser"),
        os.path.join(os.environ.get("HOME", "/root"), ".npm-global", "bin", "agent-browser"),
        "/usr/local/bin/agent-browser",
        "/usr/bin/agent-browser",
        "/usr/local/lib/node_modules/agent-browser/bin/agent-browser.js",
    ]:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which("agent-browser")


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

def patch_webui_title(binary_path: Optional[Path] = None, title_str: Optional[str] = None, log_file: Optional[Path] = None) -> bool:
    """Patch the HTML head title in OpenCode CLI binary while keeping total file byte size unchanged."""
    if binary_path is None:
        binary_path = OPENCODE_HOME / "bin" / "opencode"
    if not binary_path.exists():
        return False

    if title_str is None:
        title_str = os.getenv("OPENCODE_WEBUI_TITLE", "").strip()
    if not title_str or title_str == "OpenCode":
        return True

    try:
        with open(binary_path, "rb") as f:
            content = f.read()

        prefix = b"<title>OpenCode</title>"
        idx = content.find(prefix)
        if idx == -1:
            target_tag = f"<title>{title_str}</title>".encode("utf-8")
            if target_tag in content:
                log(f"WebUI HTML title is already patched to '{title_str}'", "INFO", log_file)
                return True
            import re
            m = re.search(rb"<title>.*?</title>", content)
            if not m:
                log("HTML <title> tag pattern not found in OpenCode binary", "WARN", log_file)
                return False
            idx = m.start()
            prefix = m.group(0)

        window_size = 350
        old_block = content[idx:idx + window_size]
        tail = old_block[len(prefix):]
        new_tag = f"<title>{title_str}</title>".encode("utf-8")
        new_block = new_tag + tail

        if len(new_block) > len(old_block):
            new_block = new_block[:len(old_block)]
        else:
            new_block = new_block + b" " * (len(old_block) - len(new_block))

        new_content = content[:idx] + new_block + content[idx + window_size:]
        if len(new_content) != len(content):
            log(f"Patch error: file size mismatch ({len(content)} != {len(new_content)})", "WARN", log_file)
            return False

        # Kill running processes so Linux releases the binary file handle
        subprocess.run(["pkill", "-f", "opencode web"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

        with open(binary_path, "wb") as f:
            f.write(new_content)

        log(f"Successfully patched WebUI HTML title to '{title_str}'", "INFO", log_file)
        return True
    except Exception as e:
        log(f"Error patching WebUI title: {e}", "WARN", log_file)
        return False

def restart_webui(port: int = 4096, log_file: Optional[Path] = None) -> None:
    """Restart OpenCode WebUI"""
    patch_webui_title(log_file=log_file)
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

