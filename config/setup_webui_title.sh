#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch the OpenCode WebUI HTML title in the OpenCode CLI binary."
    )
    parser.add_argument(
        "--title",
        dest="title",
        help="OpenCode WebUI title string. Overrides OPENCODE_WEBUI_TITLE.",
    )
    parser.add_argument(
        "--home",
        dest="home",
        default=os.getenv("ACTUAL_HOME", "/headless"),
        help="Container home path where /Desktop/config is mounted.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    title = args.title or os.getenv("OPENCODE_WEBUI_TITLE", "OpenCode")
    home = Path(args.home)
    config_dir = home / "Desktop" / "config"

    if not title or title == "OpenCode":
        print("[INFO] OPENCODE_WEBUI_TITLE is not set or using default; skipping WebUI title patch.")
        return 0

    if not config_dir.exists():
        print(f"[WARN] Config directory not found: {config_dir}; skipping title patch.")
        return 0

    sys.path.insert(0, str(config_dir))
    try:
        from opencode_utils import patch_webui_title
    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] Failed to import opencode_utils from {config_dir}: {exc}")
        return 1

    os.environ["OPENCODE_WEBUI_TITLE"] = title
    try:
        success = patch_webui_title()
        if success:
            print(f"[INFO] OpenCode WebUI title patch completed: {title}")
            return 0
        print("[WARN] OpenCode WebUI title patch did not apply.")
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] Failed to patch OpenCode WebUI title: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
