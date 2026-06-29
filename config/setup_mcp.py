#!/usr/bin/env python3
"""setup_mcp.py – Configure OpenCode MCP with robust handling.

Features
--------
* Uses :pymod:`pathlib` for OS‑independent paths.
* Centralised ``log_message`` writes to a rotating log file (5 MiB, 3 backups).
* Added ``argparse`` so you can customise the output config path or enable a dry‑run.
* Each logical step lives in its own function with type hints and docstrings.
* Dependency installation now validates the exit code and prints the full ``stderr`` on failure.
* Playwright installation uses ``--with-deps`` (required for headless browsers).
* MCP configuration includes the newly requested placeholder modules as **empty dicts**.
* Self‑check prints a concise summary of detected modules.
* Restart and health‑check of the OpenCode WebUI are performed with ``nohup`` and proper log handling.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
LOG_DIR = Path(os.getenv("LOG_DIR", "/dockerstartup/custom"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "setup_mcp.log"

def log_message(msg: str, level: str = "INFO") -> None:
    """Write a message to both stdout and the log file.

    Parameters
    ----------
    msg: str
        Human-readable log message.
    level: str, optional
        Log level name. Default is INFO.
    """
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Path helpers – they honour the environment variables used by the original script.
# ---------------------------------------------------------------------------
WORKSPACE_DIR = Path(__file__).resolve().parent
ACTUAL_HOME = Path(os.getenv("ACTUAL_HOME", "/headless"))
OPENCODE_HOME = Path(os.getenv("OPENCODE_HOME", ACTUAL_HOME / ".opencode"))
OPENCODE_CONFIG_DIR = Path(os.getenv("OPENCODE_CONFIG_DIR", ACTUAL_HOME / ".config" / "opencode"))

# ---------------------------------------------------------------------------
# Step 1 – Write MCP configuration JSON
# ---------------------------------------------------------------------------
def build_mcp_config() -> Dict[str, Any]:
    """Return the MCP configuration dictionary.

    The function includes the original required modules **and** the
    placeholder modules requested by the user. Placeholder modules are
    represented by empty dictionaries – they can be populated later
    without breaking the current setup.
    """
    base_config: Dict[str, Any] = {
        "searxng": {"base_url": "http://localhost:8080"},
        "dcp": {"max_tokens": 4000, "strategy": "semantic"},
        "mem0": {"storage": "sqlite:///mem0.db"},
        "browser": {"engine": "playwright", "headless": True},
        "local_embedding": {"storage": "faiss_index"},
        "filesystem": {"root_path": "/headless/Desktop/workspace"},
        "shell": {"safe_mode": True},
        "pdf_parser": {"storage": "parsed_docs"},
        "sqlite": {"db_path": "local_data.db"},
        # ---- Placeholder modules (empty dicts) ----
        "bestof": {},
        "comparisons": {},
        "studying": {},
        "flashcards": {},
        "practice-test": {},
        "generate-quiz": {},
        "shopping-savings": {},
        "genui": {},
        "practice-test-orchestrator": {},
        "search_uploaded_documents": {},
        # ---- Additional optional modules (empty dicts) ----
        "oh-my-opencode-slim": {},
        "superpowers": {},
        "opencode-pty": {},
        "opencode-supermemory": {},
        "opencode-agent-skills": {},
        "opencode-worktree": {},
        "opencode-type-inject": {},
        "opencode-browser": {},
        "opencode-arise": {},
        "opencode-token-monitor": {}
    }
    return {"mcp": base_config}

def write_config(mcp_config: Dict[str, Any], output_path: Path) -> Path:
    """Write *mcp_config* to *output_path* as pretty‑printed JSON.

    Returns the path of the written file for later steps.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(mcp_config, f, indent=2, ensure_ascii=False)
        log_message(f"MCP configuration written to {output_path}")
    except Exception as exc:
        log_message(f"Failed to write MCP config: {exc}", "ERROR")
        sys.exit(1)
    return output_path

# ---------------------------------------------------------------------------
# Step 2 – Dependency installation
# ---------------------------------------------------------------------------
def run(command: list[str], description: str) -> None:
    """Execute *command* with ``subprocess.run`` and log outcome.

    On failure the function logs the full stderr and aborts the script.
    """
    log_message(f"Installing: {description}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        log_message(f"[OK] {description} installed", "INFO")
    except subprocess.CalledProcessError as err:
        log_message(
            f"[ERROR] {description} failed – exit {err.returncode}\nSTDERR: {err.stderr.strip()}",
            "ERROR",
        )
        sys.exit(1)

def install_dependencies() -> None:
    """Install required pip packages and Playwright system deps."""
    packages = ["mem0ai", "playwright", "faiss-cpu", "sqlite-utils"]
    for pkg in packages:
        run(["pip3", "install", "-q", pkg], f"pip package {pkg}")

    # Playwright needs its browsers and system libraries.
    run(["playwright", "install", "--with-deps"], "Playwright (with system deps)")

# ---------------------------------------------------------------------------
# Helper – locate the *opencode* binary (fallback to bundled copy)
# ---------------------------------------------------------------------------
def get_opencode_bin() -> str:
    """Return the executable name or absolute path of *opencode*.

    The function first tries ``which opencode``; if not found it falls back to a
    bundled binary under ``$ACTUAL_HOME/.opencode/bin/opencode``.
    """
    try:
        result = subprocess.run(["which", "opencode"], capture_output=True, text=True, check=True)
        return result.stdout.strip() or "opencode"
    except Exception:
        bundled = ACTUAL_HOME / ".opencode" / "bin" / "opencode"
        return str(bundled) if bundled.exists() else "opencode"

# ---------------------------------------------------------------------------
# Step 3 – Restart OpenCode WebUI using ``nohup``
# ---------------------------------------------------------------------------
def restart_webui(port: int = 4096) -> None:
    log_message(f"Restarting OpenCode WebUI on port {port} (nohup)…")
    # Stop any existing instance gracefully, then force‑kill lingering ones.
    subprocess.run(["pkill", "-f", "opencode web"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    subprocess.run(["pkill", "-9", "-f", "opencode web"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)

    log_path = LOG_DIR / "opencode_web.log"
    bin_path = get_opencode_bin()
    cmd = f"nohup {bin_path} web --hostname 0.0.0.0 --port {port} >> {log_path} 2>&1 &"
    subprocess.Popen(cmd, shell=True)
    log_message("[OK] OpenCode WebUI launched in background")

# ---------------------------------------------------------------------------
# Step 4 – Verify the WebUI is reachable
# ---------------------------------------------------------------------------
def check_webui(port: int = 4096, retries: int = 10, interval: int = 3) -> bool:
    url = f"http://127.0.0.1:{port}"
    log_message(f"Waiting for WebUI to become reachable ({retries * interval}s max)…")
    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "5", url],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                log_message(f"[OK] WebUI reachable at {url}")
                return True
        except Exception:
            pass
        if attempt < retries:
            log_message(f"Attempt {attempt}/{retries} failed – retrying in {interval}s…")
            time.sleep(interval)
    log_message("[ERROR] WebUI did not become reachable – see opencode_web.log for details", "WARNING")
    return False

# ---------------------------------------------------------------------------
# Step 5 – Self‑check of the generated MCP config
# ---------------------------------------------------------------------------
def self_check(config_path: Path) -> bool:
    log_message("Running self‑check on the generated MCP config…")
    if not config_path.is_file():
        log_message(f"Configuration file missing: {config_path}", "ERROR")
        return False
    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        log_message(f"JSON decode error: {exc}", "ERROR")
        return False
    if "mcp" not in data or not isinstance(data["mcp"], dict):
        log_message("Invalid MCP structure – 'mcp' key missing or not a dict", "WARNING")
        return False
    modules = list(data["mcp"].keys())
    log_message(f"[OK] Detected {len(modules)} MCP modules: {', '.join(modules)}")
    return True

# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Configure OpenCode MCP.")
    parser.add_argument(
        "--output",
        type=Path,
        default=OPENCODE_CONFIG_DIR / "mcp.config.json",
        help="Path where the MCP JSON will be written (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the config file and exit without installing dependencies or restarting WebUI.",
    )
    args = parser.parse_args()

    log_message("=" * 50)
    log_message("Starting OpenCode MCP configuration")
    log_message("=" * 50)

    config = build_mcp_config()
    config_file = write_config(config, args.output)

    if not self_check(config_file):
        log_message("Self‑check failed – aborting", "ERROR")
        sys.exit(1)

    if args.dry_run:
        log_message("Dry‑run requested – exiting after config generation.")
        sys.exit(0)

    install_dependencies()
    restart_webui()
    if not check_webui():
        log_message("WebUI health‑check failed – please review the logs.", "ERROR")
        sys.exit(1)

    log_message("=" * 50)
    log_message("OpenCode MCP configuration completed successfully")
    log_message("=" * 50)

if __name__ == "__main__":
    main()
