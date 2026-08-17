#!/usr/bin/env python3
"""Install agent-browser CLI and prepare it for OpenCode MCP integration."""

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path

AGENT_BROWSER_VERSION = os.getenv("AGENT_BROWSER_VERSION", "v0.33.2")
RELEASE_API = f"https://api.github.com/repos/vercel-labs/agent-browser/releases/tags/{AGENT_BROWSER_VERSION}"

INSTALL_PATH = Path(
    os.getenv("AGENT_BROWSER_INSTALL_PATH", "/usr/local/bin/agent-browser")
)
DOWNLOAD_CACHE = Path(
    os.getenv("AGENT_BROWSER_DOWNLOAD_CACHE", "/tmp/agent-browser-download")
)

LOG_PATH = (
    Path(os.getenv("LOG_DIR", "/dockerstartup/custom")) / "setup_agent_browser.log"
)

ASSET_MAP = {
    ("Linux", "x86_64"): "agent-browser-linux-x64",
    ("Linux", "aarch64"): "agent-browser-linux-arm64",
    ("Linux", "arm64"): "agent-browser-linux-arm64",
    ("Darwin", "x86_64"): "agent-browser-darwin-x64",
    ("Darwin", "arm64"): "agent-browser-darwin-arm64",
}


def log(message: str, level: str = "INFO") -> None:
    line = f"[{level}] {message}"
    print(line)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass


def current_asset_name() -> str:
    system = platform.system()
    machine = platform.machine()
    return ASSET_MAP.get((system, machine), "")


def run_command(cmd, cwd=None, timeout=300):
    log(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr or result.stdout or f"Command failed: {' '.join(cmd)}"
        )
    return result.stdout.strip()


def download_asset(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        log(f"Asset already downloaded: {dest}")
        return
    if shutil.which("curl"):
        run_command(["curl", "-fsSL", "-o", str(dest), url])
    elif shutil.which("wget"):
        run_command(["wget", "-qO", str(dest), url])
    else:
        import urllib.request

        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                data = response.read()
            dest.write_bytes(data)
        except Exception as exc:
            raise RuntimeError(
                "Failed to download agent-browser asset with urllib: %s" % exc
            )


def fetch_release_metadata() -> dict:
    try:
        output = run_command(["curl", "-fsSL", RELEASE_API])
        return json.loads(output)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch agent-browser release metadata: {exc}"
        ) from exc


def install_binary(asset_name: str, download_url: str) -> None:
    DOWNLOAD_CACHE.mkdir(parents=True, exist_ok=True)
    target_archive = DOWNLOAD_CACHE / asset_name
    if not target_archive.exists():
        if shutil.which("curl"):
            run_command(["curl", "-fsSL", "-o", str(target_archive), download_url])
        elif shutil.which("wget"):
            run_command(["wget", "-qO", str(target_archive), download_url])
        else:
            raise RuntimeError(
                "Neither curl nor wget is available to download agent-browser"
            )
    else:
        log(f"Using cached asset: {target_archive}")

    install_parent = INSTALL_PATH.parent
    install_parent.mkdir(parents=True, exist_ok=True)
    target_archive.chmod(target_archive.stat().st_mode | stat.S_IEXEC)
    target_archive.rename(INSTALL_PATH)
    INSTALL_PATH.chmod(0o755)
    log(f"Installed agent-browser binary to {INSTALL_PATH}")


def link_binary() -> None:
    if not INSTALL_PATH.exists():
        raise RuntimeError(f"agent-browser binary not found at {INSTALL_PATH}")
    symlink = Path("/usr/local/bin/agent-browser")
    if symlink.exists() and symlink.resolve() != INSTALL_PATH.resolve():
        symlink.unlink()
    if not symlink.exists():
        symlink.symlink_to(INSTALL_PATH)
    log(f"Symlinked {symlink} -> {INSTALL_PATH}")


def agent_browser_installed() -> bool:
    return shutil.which("agent-browser") is not None


def install_chrome_deps() -> None:
    if not shutil.which("agent-browser"):
        log("agent-browser CLI not installed; cannot install browser deps", "WARN")
        return
    try:
        run_command(["agent-browser", "install", "--with-deps"])
        log("agent-browser browser runtime and system deps installed successfully")
    except Exception as exc:
        log(f"agent-browser install --with-deps failed: {exc}", "WARN")


def main() -> None:
    if agent_browser_installed():
        log("agent-browser already installed")
        return

    asset_name = current_asset_name()
    if not asset_name:
        raise RuntimeError(
            f"Unsupported platform {platform.system()} {platform.machine()}"
        )

    metadata = fetch_release_metadata()
    assets = metadata.get("assets", [])
    asset = next((a for a in assets if a.get("name") == asset_name), None)
    if not asset:
        raise RuntimeError(
            f"Release asset {asset_name} not found in agent-browser release {AGENT_BROWSER_VERSION}"
        )

    download_url = asset.get("browser_download_url")
    if not download_url:
        raise RuntimeError("No browser_download_url found for selected asset")

    install_binary(asset_name, download_url)
    link_binary()
    install_chrome_deps()

    log("agent-browser installation completed")


if __name__ == "__main__":
    try:
        import shutil

        main()
    except Exception as exc:
        log(str(exc), "ERROR")
        sys.exit(1)
