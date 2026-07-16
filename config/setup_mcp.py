#!/usr/bin/env python3
"""setup_mcp.py – Configure OpenCode MCP servers.

Writes MCP server configuration into ~/.config/opencode/opencode.jsonc.
Uses bunx (full path) for MCP server execution.
"""

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ACTUAL_HOME = Path(os.getenv("ACTUAL_HOME", "/headless"))
OPENCODE_CONFIG_DIR = Path(os.getenv("OPENCODE_CONFIG_DIR", ACTUAL_HOME / ".config" / "opencode"))
OPENCODE_CONFIG_FILE = OPENCODE_CONFIG_DIR / "opencode.jsonc"
DEFAULT_LOG_DIR = Path(os.getenv("LOG_DIR", "/dockerstartup/custom"))
try:
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR = DEFAULT_LOG_DIR
except OSError:
    LOG_DIR = Path("/tmp/opencode-mcp")
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

    path_bunx = shutil.which("bunx")
    if path_bunx:
        return path_bunx

    return None


def _ensure_bunx() -> str:
    """Find bunx or install it if missing."""
    bunx_path = _find_bunx()
    if bunx_path:
        return bunx_path

    log("bunx not found, attempting to install bun@latest...")
    try:
        result = subprocess.run(
            ["npm", "install", "-g", "bun"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError:
        log("npm not found in PATH. Install Node.js/npm or set BUNX env var.", "ERROR")
        raise RuntimeError("npm not found: please install Node.js and npm, or provide bunx path via BUNX env var")
    except Exception as e:
        log(f"ERROR running npm install: {e}", "ERROR")
        raise RuntimeError("Failed to run npm to install bun") from e

    if result.returncode != 0:
        log(f"npm install failed: {result.stderr[:500]}", "ERROR")
        raise RuntimeError("Failed to install bun via npm")

    bunx_path = _find_bunx()
    if not bunx_path:
        raise RuntimeError("bunx still not found after npm install")

    log(f"Successfully installed bun, bunx at: {bunx_path}")
    return bunx_path


# BUNX resolution is performed at runtime in main()


# ---------------------------------------------------------------------------
# MCP servers
# ---------------------------------------------------------------------------
def build_mcp_servers(bunx_path: str) -> dict:
    """Return the MCP_SERVERS dict using the provided bunx executable path."""
    workspace_dir = os.getenv("MCP_WORKSPACE_PATH", "/headless/Desktop/workspace")
    pdf_port = os.getenv("MCP_PDF_PORT", "3002")
    debug_port = os.getenv("MCP_DEBUG_PORT", "3003")
    system_monitor_port = os.getenv("MCP_SYSTEM_MONITOR_PORT", "3004")
    sqlite_port = os.getenv("MCP_SQLITE_PORT", "3100")
    sqlite_db_path = os.getenv("MCP_SQLITE_DB_PATH", str(OPENCODE_CONFIG_DIR / "opencode.sqlite"))

    return {
        "filesystem": {
            "type": "local",
            "command": [bunx_path, "@modelcontextprotocol/server-filesystem", workspace_dir],
            "enabled": True,
        },
        # Postgres removed by default (not necessary for local dev)
        "puppeteer": {
            "type": "local",
            "command": [bunx_path, "@modelcontextprotocol/server-puppeteer"],
            "enabled": True,
            "env": {
                "ALLOW_DANGEROUS": "true",
                "PUPPETEER_LAUNCH_OPTIONS": '{"args": ["--no-sandbox"]}'
            }
        },
        "memory": {
            "type": "local",
            "command": [bunx_path, "@modelcontextprotocol/server-memory"],
            "enabled": True,
        },
        # SQLite-based memory for session compression / persistent small storage
        "sqlite": {
            "type": "remote",
            "url": f"http://127.0.0.1:{sqlite_port}/mcp",
            "enabled": True,
            "headers": {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            "_package": "@pepk/mcp-memory-sqlite",
            "_args": ["--transport", "http", "--port", str(sqlite_port)],
            "_env": {"MCP_SQLITE_DB_PATH": sqlite_db_path},
        },
        "sequential-thinking": {
            "type": "local",
            "command": [bunx_path, "@modelcontextprotocol/server-sequential-thinking"],
            "enabled": True,
        },
        "gh_grep": {
            "type": "local",
            "command": [bunx_path, "@modelcontextprotocol/server-github"],
            "enabled": True,
        },
        # These services expose HTTP MCP endpoints, so OpenCode should connect to them as remote servers.
        "pdf": {
            "type": "remote",
            "url": f"http://127.0.0.1:{pdf_port}/mcp",
            "enabled": True,
            "_package": "@modelcontextprotocol/server-pdf",
            "_env": {"PORT": str(pdf_port)},
        },
        "debug": {
            "type": "remote",
            "url": f"http://127.0.0.1:{debug_port}/mcp",
            "enabled": True,
            "_package": "@modelcontextprotocol/server-debug",
            "_env": {"PORT": str(debug_port)},
        },
        "system-monitor": {
            "type": "remote",
            "url": f"http://127.0.0.1:{system_monitor_port}/mcp",
            "enabled": True,
            "_package": "@modelcontextprotocol/server-system-monitor",
            "_env": {"PORT": str(system_monitor_port)},
        },
    }


def _npm_available() -> bool:
    """Return True if `npm` is available in PATH."""
    return shutil.which("npm") is not None


def _package_exists(pkg_name: str) -> Optional[bool]:
    """Check npm registry for package existence using `npm view <pkg> version`.

    Returns True if package exists, False if it does not, or None if check
    couldn't be performed (e.g., npm missing or network error).
    """
    if not _npm_available():
        log("npm not available; skipping package existence checks", "WARN")
        return None
    try:
        result = subprocess.run(["npm", "view", pkg_name, "version"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            return True
        return False
    except Exception as e:
        log(f"Error checking npm package {pkg_name}: {e}", "WARN")
        return None


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def ensure_remote_mcp_servers(servers: dict, bunx_path: str) -> None:
    """Start HTTP-based MCP servers that OpenCode should connect to remotely."""
    for name, cfg in servers.items():
        if cfg.get("type") != "remote" or not cfg.get("enabled"):
            continue
        package = cfg.get("_package")
        if not package:
            continue

        url = cfg.get("url", "")
        if not url.startswith("http://"):
            continue
        port = None
        try:
            port = int(url.rsplit(":", 1)[1].split("/", 1)[0])
        except ValueError:
            continue

        if _port_open("127.0.0.1", port):
            log(f"MCP server {name} already reachable at {url}")
            continue

        log(f"Starting remote MCP server {name} at {url}")
        log_path = LOG_DIR / f"{name}_mcp.log"
        env = os.environ.copy()
        for key, value in cfg.get("_env", {}).items():
            env[key] = str(value)

        if name == "sqlite" and "MCP_SQLITE_DB_PATH" in env:
            sqlite_dir = str(Path(env["MCP_SQLITE_DB_PATH"]).parent)
            os.makedirs(sqlite_dir, exist_ok=True)

        cmd = [bunx_path, package]
        if cfg.get("_args"):
            cmd.extend(cfg["_args"])

        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(f"--- starting {name} ---\n")
        subprocess.Popen(
            cmd,
            env=env,
            stdout=open(log_path, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=str(ACTUAL_HOME),
            start_new_session=True,
        )
        for _ in range(10):
            if _port_open("127.0.0.1", port):
                break
            time.sleep(1)

        if _port_open("127.0.0.1", port):
            log(f"Remote MCP server {name} started successfully")
        else:
            log(f"Remote MCP server {name} did not become reachable at {url}", "WARN")


def validate_servers(servers: dict, skip_validate: bool = False) -> None:
    """Validate MCP server packages and mark missing ones disabled.

    If validation cannot be performed, leaves servers unchanged.
    """
    if skip_validate:
        log("Skipping MCP package validation (--skip-validate)")
        return

    for name, cfg in servers.items():
        cmd = cfg.get("command") or []
        if not cmd:
            continue
        # find package-like token in command (e.g. @modelcontextprotocol/server-*)
        pkg = None
        for token in cmd:
            if not isinstance(token, str):
                continue
            stripped = token.strip()
            if stripped.startswith("@") or stripped.startswith("modelcontextprotocol") or stripped.startswith("server-"):
                pkg = stripped
                break
        if not pkg:
            continue
        exists = _package_exists(pkg)
        if exists is False:
            log(f"Package not found on npm: {pkg}; disabling MCP server: {name}", "WARN")
            cfg["enabled"] = False
            cfg["_note"] = "package not found on npm"
        elif exists is None:
            log(f"Could not verify package {pkg}; leaving enabled state as-is for {name}", "WARN")


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
base_config = {
    "searxng": {"base_url": "http://localhost:8080"},
    "dcp": {"max_tokens": 4000, "strategy": "semantic"},
    "mem0": {"storage": "sqlite:///mem0.db"},
    "browser": {"engine": "playwright", "headless": True},
    "local_embedding": {"storage": "faiss_index"},
    "local_llm": {"engine": "ollama", "model": "qwen2.5-coder:32b"},
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


def build_config(existing: dict, servers: dict) -> dict:
    existing["mcp"] = servers
    existing.pop("base_config", None)
    return existing


def write_config(config: dict) -> None:
    OPENCODE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        content = json.dumps(config, indent=2, ensure_ascii=False)
        with open(OPENCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        # Verify write
        verify = json.loads(OPENCODE_CONFIG_FILE.read_text(encoding="utf-8"))
        assert "mcp" in verify and len(verify["mcp"]) == len(config["mcp"])
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
    parser.add_argument("--skip-validate", action="store_true", help="Skip npm package existence validation")
    parser.add_argument("--no-restart", action="store_true", help="Skip restart")
    args = parser.parse_args()

    log("=" * 50)
    log("OpenCode MCP Configuration")
    log("=" * 50)

    # 1. Read existing config
    existing = read_existing_config()

    # 1.5 Determine bunx (allow env override)
    env_bunx = os.getenv("BUNX")
    if env_bunx:
        if os.path.isfile(env_bunx) and os.access(env_bunx, os.X_OK):
            BUNX = env_bunx
            log(f"Using bunx from BUNX env: {BUNX}")
        else:
            log(f"BUNX env provided but not executable: {env_bunx}", "ERROR")
            raise RuntimeError(f"BUNX env provided but not executable: {env_bunx}")
    else:
        BUNX = _ensure_bunx()
        log(f"Using bunx: {BUNX}")

    # 2. Build servers with resolved bunx
    servers = build_mcp_servers(BUNX)

    # 3. Validate MCP packages (may mark some servers disabled)
    validate_servers(servers, skip_validate=getattr(args, "skip_validate", False))

    # 3.5 Start remote MCP servers that OpenCode should connect to
    ensure_remote_mcp_servers(servers, BUNX)

    # 4. Merge & write config
    config = build_config(existing, servers)

    # 2. Write & verify
    write_config(config)
    log(f"MCP servers: {', '.join(servers.keys())}")

    if args.dry_run:
        log("Dry run complete")
        return

    if args.no_restart:
        log("Skipping restart because --no-restart was provided")
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
