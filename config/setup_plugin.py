#!/usr/bin/env python3
"""
OpenCode Plugin 安装和配置脚本
用于安装和管理 OpenCode 的各类插件
"""

import os
import json
import subprocess
import time
import sys
import concurrent.futures
from opencode_utils import (
    OPENCODE_HOME, get_log_file, log as _log, 
    command_exists, restart_webui
)

LOG_FILE = get_log_file("setup_plugin")
OPENCODE_PLUGINS_DIR = os.path.join(OPENCODE_HOME, "plugins")
PLUGINS_LIST_FILE = os.path.join(OPENCODE_HOME, "plugins.json")

def log(msg, level="INFO"):
    _log(msg, level, LOG_FILE)


# Plugin 清单
PLUGINS = [
    "oh-my-opencode-slim@git+https://github.com/alvinunreal/oh-my-opencode-slim.git",
    "superpowers@git+https://github.com/obra/superpowers.git",
    "opencode-pty@git+https://github.com/shekohex/opencode-pty.git",
    "opencode-supermemory@git+https://github.com/supermemoryai/opencode-supermemory.git",
    "@morphllm/opencode-morph-plugin@git+https://github.com/morphllm/opencode-morph-plugin.git",
    "opencode-agent-skills@git+https://github.com/joshuadavidthomas/opencode-agent-skills.git",
    "opencode-worktree@git+https://github.com/kdcokenny/opencode-worktree.git",
    "@nick-vi/opencode-type-inject@git+https://github.com/nick-vi/type-inject.git",
    "opencode-browser@git+https://github.com/different-ai/opencode-browser.git",
    "opencode-arise@git+https://github.com/moinulmoin/opencode-arise.git",
    "opencode-token-monitor@git+https://github.com/Ainsley0917/opencode-token-monitor.git",
]


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
    """写入 plugin 清单到配置文件"""
    cleaned = [p for p in plugins if isinstance(p, str) and p]
    data = {
        "plugins": cleaned,
        "lastUpdated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(cleaned),
    }
    try:
        os.makedirs(os.path.dirname(PLUGINS_LIST_FILE), exist_ok=True)
        with open(PLUGINS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"Plugin 清单已写入: {PLUGINS_LIST_FILE}")
    except Exception as e:
        log(f"写入 Plugin 清单失败: {e}", "ERROR")
        sys.exit(1)


# -------------------------------
# 模块 3：安装 Plugin
# -------------------------------
def install_single_plugin(plugin, idx, total):
    log(f"[{idx}/{total}] 开始安装 Plugin: {plugin}")
    success = False
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        try:
            # 正确语法: opencode plugin <module> (没有 install 子命令)
            result = subprocess.run(
                ["opencode", "plugin", plugin, "--force"],
                capture_output=True,
                timeout=120,
                text=True,
            )
            if result.returncode == 0:
                log(f"  [OK] {plugin} 安装成功")
                return (plugin, True)
            else:
                err = (result.stderr or result.stdout or "").strip()
                first_line = err.split("\n")[0] if err else "未知错误"
                log(f"  [WARN] 尝试 {attempt}/{max_retries} - {plugin} 安装失败: {first_line}", "WARN")
        except subprocess.TimeoutExpired:
            log(f"  [WARN] 尝试 {attempt}/{max_retries} - {plugin} 安装超时 (120s)", "WARN")
        except Exception as e:
            log(f"  [WARN] 尝试 {attempt}/{max_retries} - {plugin} 安装出错: {e}", "WARN")
        
        if attempt < max_retries:
            time.sleep(2)
            
    log(f"  [ERROR] {plugin} 在 {max_retries} 次尝试后最终安装失败", "ERROR")
    return (plugin, False)

def install_plugins(plugins):
    """使用 opencode plugin <module> 命令安装插件 (并发)"""
    log(f"开始并发安装 {len(plugins)} 个 Plugin...")

    if not command_exists("opencode"):
        log("opencode 命令不可用，请确保已安装 OpenCode", "ERROR")
        sys.exit(1)

    installed = []
    failed = []
    
    max_workers = min(5, len(plugins)) if plugins else 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(install_single_plugin, plugin, idx, len(plugins)): plugin
            for idx, plugin in enumerate(plugins, 1)
        }
        
        for future in concurrent.futures.as_completed(futures):
            plugin, success = future.result()
            if success:
                installed.append(plugin)
            else:
                failed.append(plugin)

    log(f"安装总结: 成功 {len(installed)}/{len(plugins)}, 失败 {len(failed)}/{len(plugins)}")
    if failed:
        log(f"  失败的 Plugin: {', '.join(failed)}", "WARN")

    return installed, failed


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
            data["plugins"] = [p for p in data["plugins"] if isinstance(p, str) and p != "list"]
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
    restart_webui(restart, log_func=log)


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
