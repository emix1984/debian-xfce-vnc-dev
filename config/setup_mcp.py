#!/usr/bin/env python3
"""setup_mcp.py – Configure OpenCode MCP servers.

Writes MCP server configuration into ~/.config/opencode/opencode.jsonc.
Uses bunx (full path) for MCP server execution.
"""

import json
import os
import subprocess
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ACTUAL_HOME = Path(os.getenv("ACTUAL_HOME", "/headless"))
OPENCODE_CONFIG_DIR = Path(os.getenv("OPENCODE_CONFIG_DIR", ACTUAL_HOME / ".config" / "opencode"))
OPENCODE_CONFIG_FILE = OPENCODE_CONFIG_DIR / "opencode.jsonc"
LOG_DIR = Path(os.getenv("LOG_DIR", "/dockerstartup/custom"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "setup_mcp.log"
SCRIPT_DIR = Path(__file__).resolve().parent


def log(msg: str, level: str = "INFO") -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Find bunx
# ---------------------------------------------------------------------------
def _find_bunx() -> str:
    for p in [
        os.path.join(ACTUAL_HOME, ".bun", "bin", "bunx"),
        os.path.join(os.environ.get("HOME", "/root"), ".bun", "bin", "bunx"),
        "/usr/local/bin/bunx",
        "/usr/bin/bunx",
    ]:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return "bunx"


BUNX = _find_bunx()
log(f"Using bunx: {BUNX}")


# ---------------------------------------------------------------------------
# MCP servers
# ---------------------------------------------------------------------------
MCP_SERVERS = {
    "filesystem": {
        "type": "local",
        "command": [BUNX, "@modelcontextprotocol/server-filesystem", "/headless/Desktop/workspace"],
        "enabled": True,
    },
    "postgres": {
        "type": "local",
        "command": [BUNX, "@modelcontextprotocol/server-postgres"],
        "enabled": True,
    },
    "puppeteer": {
        "type": "local",
        "command": [BUNX, "@modelcontextprotocol/server-puppeteer"],
        "enabled": True,
    },
    "memory": {
        "type": "local",
        "command": [BUNX, "@modelcontextprotocol/server-memory"],
        "enabled": True,
    },
    "sequential-thinking": {
        "type": "local",
        "command": [BUNX, "@modelcontextprotocol/server-sequential-thinking"],
        "enabled": True,
    },
}


# ---------------------------------------------------------------------------
# Read existing config
# ---------------------------------------------------------------------------
def read_existing_config() -> dict:
    if not OPENCODE_CONFIG_FILE.exists():
        return {}
    try:
        content = OPENCODE_CONFIG_FILE.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as e:
        log(f"Warning: existing config invalid JSON, will overwrite: {e}", "WARN")
        return {}


# ---------------------------------------------------------------------------
# Merge & write config
# ---------------------------------------------------------------------------
def build_config(existing: dict) -> dict:
    existing["mcp"] = MCP_SERVERS
    return existing


def write_config(config: dict) -> None:
    OPENCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        content = json.dumps(config, indent=2, ensure_ascii=False)
        with open(OPENCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        # Verify write
        verify = json.loads(OPENCODE_CONFIG_FILE.read_text(encoding="utf-8"))
        assert "mcp" in verify and len(verify["mcp"]) == len(MCP_SERVERS)
        log(f"Config written and verified: {OPENCODE_CONFIG_FILE}")
    except Exception as e:
        log(f"ERROR writing config: {e}", "ERROR")
        raise


# ---------------------------------------------------------------------------
# Restart WebUI using restart_opencode.sh
# ---------------------------------------------------------------------------
def restart_webui(port: int = 4096) -> None:
    restart_script = SCRIPT_DIR / "restart_opencode.sh"
    if restart_script.exists():
        log(f"Restarting WebUI via {restart_script}...")
        result = subprocess.run(
            ["bash", str(restart_script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log(f"Restart script failed: {result.stderr[:500]}", "WARN")
        else:
            log("Restart script completed successfully")
    else:
        log(f"{restart_script} not found, restarting directly...")
        _restart_direct(port)


def _restart_direct(port: int) -> None:
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

    log_path = LOG_DIR / "opencode_web.log"
    subprocess.Popen(
        f"nohup {bin_path} web --hostname 0.0.0.0 --port {port} >> {log_path} 2>&1 &",
        shell=True,
    )
    log("[OK] WebUI launched directly")


# ---------------------------------------------------------------------------
# Verify MCP servers after restart
# ---------------------------------------------------------------------------
def verify_mcp(timeout: int = 15) -> bool:
    """Check if opencode process is running."""
    for i in range(timeout):
        try:
            result = subprocess.run(
                ["pgrep", "-f", "opencode"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                log(f"OpenCode process found: {result.stdout.strip().splitlines()[0]}")
                return True
        except Exception:
            pass
        time.sleep(1)

    log("OpenCode process not found after restart", "WARN")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Configure OpenCode MCP servers")
    parser.add_argument("--dry-run", action="store_true", help="Generate config only")
    parser.add_argument("--no-restart", action="store_true", help="Skip restart")
    args = parser.parse_args()

    log("=" * 50)
    log("OpenCode MCP Configuration")
    log("=" * 50)

    # 1. Read & merge config
    existing = read_existing_config()
    config = build_config(existing)

    # 2. Write & verify
    write_config(config)
    log(f"MCP servers: {', '.join(MCP_SERVERS.keys())}")

    if args.dry_run:
        log("Dry run complete")
        return

    # 3. Restart
    restart_webui()

    # 4. Verify
    if verify_mcp():
        log("[OK] OpenCode is running")
    else:
        log("[WARN] OpenCode may not have started correctly", "WARN")

    log("=" * 50)
    log("MCP configuration complete")
    log("=" * 50)


if __name__ == "__main__":
    main()
