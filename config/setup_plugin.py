#!/usr/bin/env python3
"""
OpenCode Plugin 安装和配置脚本
用于安装和管理 OpenCode 的各类插件
"""

import os
import json
import time
import sys
from opencode_utils import (
    OPENCODE_HOME,
    OPENCODE_CONFIG_DIR,
    OPENCODE_CONFIG_FILE,
    WORKSPACE_DIR,
    WORKSPACE_OPENCODE_DIR,
    get_log_file,
    log as _log,
    command_exists,
    restart_webui,
)

LOG_FILE = get_log_file("setup_plugin")
OPENCODE_PLUGINS_DIR = os.path.join(OPENCODE_CONFIG_DIR, "plugins")
PLUGINS_LIST_FILE = os.path.join(OPENCODE_CONFIG_DIR, "plugins.json")
WORKSPACE_PLUGINS_DIR = str(WORKSPACE_OPENCODE_DIR / "plugins")

def log(msg, level="INFO"):
    _log(msg, level, LOG_FILE)


# Plugin 清单
PLUGINS = [
    # OpenCode v2 plugins. Keep the Git/tag references used by the v2 loader.
    "oh-my-opencode-slim@2.2.25",
    "superpowers@git+https://github.com/obra/superpowers.git#v6.4.1",
    {"package": "opencode-pty/v2"},
    "opencode-supermemory",
]

# Active managed plugin package IDs
MANAGED_PLUGIN_IDS = {
    "oh-my-opencode-slim",
    "superpowers",
    "opencode-pty",
    "opencode-pty/v2",
    "opencode-supermemory",
}


def plugin_package_id(plugin):
    if isinstance(plugin, dict):
        plugin = plugin.get("package", "")
    if not isinstance(plugin, str):
        return ""
    if "@git+" in plugin:
        return plugin.split("@git+", 1)[0]
    if plugin.startswith("git+"):
        return plugin.split("#", 1)[0].rsplit("/", 1)[-1].removesuffix(".git")
    return plugin.split("@", 1)[0]


def is_managed_plugin(plugin):
    package_id = plugin_package_id(plugin)
    return any(
        package_id == managed_id or package_id.startswith(f"{managed_id}/")
        for managed_id in MANAGED_PLUGIN_IDS
    )


# -------------------------------
# 模块 1：准备 Plugin 配置目录
# -------------------------------
def prepare_plugin_dir():
    """创建 plugin 配置目录"""
    os.makedirs(OPENCODE_PLUGINS_DIR, exist_ok=True)
    log(f"Plugin 目录已准备: {OPENCODE_PLUGINS_DIR}")


# -------------------------------
# 模块 2：写入 Plugin 清单
# -------------------------------
def write_plugin_list(plugins):
    """写入 plugin 清单到配置文件 (只保留干净的包名)"""
    names = []
    for p in plugins:
        if isinstance(p, dict) and isinstance(p.get("package"), str):
            names.append(p["package"])
        elif isinstance(p, str) and p:
            name = p.split("@")[0]
            name = name.split("@")[0]
            names.append(name)
    data = {
        "plugins": names,
        "lastUpdated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(names),
    }
    try:
        os.makedirs(os.path.dirname(PLUGINS_LIST_FILE), exist_ok=True)
        with open(PLUGINS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"Plugin 清单已写入: {PLUGINS_LIST_FILE}")

        # 同步写入 OpenCode 官方识别的配置文件 opencode.jsonc
        # 注意: OpenCode 1.17.20 对第三方插件兼容性较差，若注入未经适配的插件会导致主线程事件循环彻底卡死
        # 故保持 "plugin": [] 避免 WebUI 假死与无法点击
        if OPENCODE_CONFIG_FILE.exists():
            try:
                content = json.loads(OPENCODE_CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                content = {}
            content["plugin"] = []
            content.pop("plugins", None)  # Ensure no invalid plugins key exists
            with open(OPENCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            log(f"Plugin 列表已安全写入 OpenCode 配置文件: {OPENCODE_CONFIG_FILE}")

        # 清理 ~/.opencode/opencode.json 避免读取重复或冲突的根节点
        opencode_json_path = os.path.join(OPENCODE_HOME, "opencode.json")
        try:
            with open(opencode_json_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
            log(f"重置 Clean opencode.json 成功: {opencode_json_path}")
        except Exception as e:
            log(f"清理 opencode.json 失败: {e}", "WARN")

    except Exception as e:
        log(f"写入 Plugin 清单失败: {e}", "ERROR")
        sys.exit(1)


def v2_plugin_reference(plugin):
    """Keep v2 package specifiers and package-option objects intact."""
    return plugin




# Removed legacy v1 registration/import helpers. Plugin package installation is
# managed by OpenCode v2 from the global `plugins` config array.


def install_plugins(plugins):
    """Register v2 package plugins in the global OpenCode configuration."""
    os.makedirs(OPENCODE_CONFIG_DIR, exist_ok=True)
    try:
        config = {}
        if os.path.exists(OPENCODE_CONFIG_FILE):
            with open(OPENCODE_CONFIG_FILE, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        config["$schema"] = "https://opencode.ai/config.json"
        existing_plugins = config.get("plugins", [])
        if not isinstance(existing_plugins, list):
            existing_plugins = []
        existing_plugins = [
            plugin for plugin in existing_plugins
            if not is_managed_plugin(plugin)
        ]
        plugin_entries = []
        seen_entries = set()
        for plugin in [*existing_plugins, *plugins]:
            if not (
                (isinstance(plugin, str) and plugin)
                or (isinstance(plugin, dict) and isinstance(plugin.get("package"), str))
            ):
                continue
            reference = v2_plugin_reference(plugin)
            key = json.dumps(reference, sort_keys=True)
            if key not in seen_entries:
                seen_entries.add(key)
                plugin_entries.append(reference)
        config["plugins"] = plugin_entries
        with open(OPENCODE_CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=False)
        log(f"v2 plugin 配置已写入: {OPENCODE_CONFIG_FILE}")
        return plugins, []
    except Exception as error:
        log(f"写入 v2 plugin 配置失败: {error}", "ERROR")
        return [], plugins


# -------------------------------
# 模块 4：自检 Plugin 配置
# -------------------------------
def self_check():
    """验证 plugin 配置文件结构"""
    log("正在自检 Plugin 配置...")

    if not os.path.exists(PLUGINS_LIST_FILE):
        log(f"Plugin 配置文件不存在: {PLUGINS_LIST_FILE}", "WARN")
        return False

    try:
        with open(PLUGINS_LIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 确保 plugins 字段是列表，过滤无效条目
        if isinstance(data.get("plugins"), list):
            data["plugins"] = [
                p for p in data["plugins"] if isinstance(p, str) and p != "list"
            ]
        else:
            data["plugins"] = []

        # 写回修复后的结构
        with open(PLUGINS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        plugins = data["plugins"]
        log(f"[OK] Plugin 配置文件结构正确，共 {len(plugins)} 个 Plugin")
        if plugins:
            log(f"Plugin 清单 (最后更新: {data.get('lastUpdated', 'N/A')}):")
            for p in plugins:
                log(f"  - {p}")
        else:
            log("[WARN] 配置中没有任何 Plugin", "WARN")

        return True

    except json.JSONDecodeError as e:
        log(f"JSON 解析失败: {e}", "ERROR")
        return False
    except Exception as e:
        log(f"自检失败: {e}", "ERROR")
        return False


# -------------------------------
# 模块 5：重启 WebUI（可选）
# -------------------------------
def do_restart_webui(restart=False):
    if not restart:
        log("跳过 WebUI 重启（可选）")
        return
    restart_webui(4096, LOG_FILE)


# -------------------------------
# 主入口
# -------------------------------
def main():
    log("=" * 60)
    log("OpenCode Plugin 安装和配置脚本")
    log("=" * 60)

    # 1. 准备目录
    prepare_plugin_dir()

    # 2. 写入 Plugin 清单
    write_plugin_list(PLUGINS)

    # 3. 自检配置
    if not self_check():
        log("配置检查失败", "ERROR")
        sys.exit(1)

    # 4. 检查 OpenCode 是否已安装
    if not command_exists("opencode"):
        log("[WARN] OpenCode 未安装，跳过 Plugin 安装步骤", "WARN")
        log("请先运行 container-init.sh 或手动安装 OpenCode")
    else:
        # 5. 安装 Plugin
        install_plugins(PLUGINS)

        # 6. 可选：重启 WebUI（默认不重启）
        do_restart_webui(restart=False)

    log("=" * 60)
    log("OpenCode Plugin 配置完成")
    log("=" * 60)
    log(f"详细日志: {LOG_FILE}")


if __name__ == "__main__":
    main()
