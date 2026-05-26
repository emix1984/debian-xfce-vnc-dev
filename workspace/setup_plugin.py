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

# =====================================
# OpenCode 路径配置 - 在 consol/debian-xfce-vnc 容器中
# =====================================
# consol/debian-xfce-vnc 容器中 root 用户的 HOME 是 /headless
ACTUAL_HOME = os.environ.get("ACTUAL_HOME", "/headless")
OPENCODE_HOME = os.environ.get("OPENCODE_HOME", os.path.join(ACTUAL_HOME, ".opencode"))
OPENCODE_CONFIG_DIR = os.environ.get("OPENCODE_CONFIG_DIR", os.path.join(ACTUAL_HOME, ".config", "opencode"))
OPENCODE_PLUGINS_DIR = os.path.join(OPENCODE_HOME, "plugins")
PLUGINS_LIST_FILE = os.path.join(OPENCODE_HOME, "plugins.json")

# 将 OpenCode 的 bin 目录加入 PATH，确保后续命令可直接调用 opencode
os.environ["PATH"] = os.path.join(OPENCODE_HOME, "bin") + ":" + os.environ.get("PATH", "")

# 日志配置 - 日志文件固定存放在 /dockerstartup/custom
LOG_DIR = os.environ.get("LOG_DIR", "/dockerstartup/custom")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "setup_plugin.log")


def log(msg, level="INFO"):
    """打印日志到标准输出，并同时写入日志文件"""
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def command_exists(cmd):
    """检查命令是否存在"""
    try:
        r = subprocess.run(["which", cmd], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


# Plugin 清单
PLUGINS = [
    "oh-my-opencode-slim",
    "superpowers@git+https://github.com/obra/superpowers.git",
    "opencode-pty",
    "opencode-supermemory",
    "@morphllm/opencode-morph-plugin",
    "opencode-agent-skills",
    # "opencode-worktree",      # package has no OpenCode plugin entrypoints
    # "opencode-type-inject",   # package not found on npm
    "opencode-browser",
    "opencode-arise",
    "opencode-token-monitor",
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
def install_plugins(plugins):
    """使用 opencode plugin <module> 命令安装插件"""
    log(f"开始安装 {len(plugins)} 个 Plugin...")

    if not command_exists("opencode"):
        log("opencode 命令不可用，请确保已安装 OpenCode", "ERROR")
        sys.exit(1)

    installed = []
    failed = []

    for idx, plugin in enumerate(plugins, 1):
        log(f"[{idx}/{len(plugins)}] 安装 Plugin: {plugin}")
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
                installed.append(plugin)
            else:
                err = (result.stderr or result.stdout or "").strip()
                # 只取错误信息的第一行，避免输出过长
                first_line = err.split("\n")[0] if err else "未知错误"
                log(f"  [WARN] {plugin} 安装失败: {first_line}", "WARN")
                failed.append(plugin)
        except subprocess.TimeoutExpired:
            log(f"  [WARN] {plugin} 安装超时 (120s)", "WARN")
            failed.append(plugin)
        except Exception as e:
            log(f"  [WARN] {plugin} 安装出错: {e}", "WARN")
            failed.append(plugin)

        time.sleep(1)

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
def restart_webui(restart=False):
    """重启 OpenCode WebUI 以应用新 Plugin"""
    if not restart:
        log("跳过 WebUI 重启（可选）")
        return

    port = 4096
    webui_log = os.path.join(LOG_DIR, "opencode_web.log")

    log("正在重启 OpenCode WebUI...")

    # 停止现有进程
    subprocess.run(["pkill", "-f", "opencode web"], capture_output=True)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", "opencode web"], capture_output=True)
    time.sleep(1)

    # 启动新实例
    try:
        cmd = f"nohup opencode web --hostname 0.0.0.0 --port {port} >> {webui_log} 2>&1 &"
        subprocess.Popen(cmd, shell=True)
        log(f"[OK] OpenCode WebUI 已重启 (端口 {port})")
    except Exception as e:
        log(f"启动 OpenCode WebUI 失败: {e}", "ERROR")


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
        log("请先运行 init.sh 或手动安装 OpenCode")
    else:
        # 5. 安装 Plugin
        install_plugins(PLUGINS)

        # 6. 可选：重启 WebUI（默认不重启）
        restart_webui(restart=False)

    log("=" * 60)
    log("OpenCode Plugin 配置完成")
    log("=" * 60)
    log(f"详细日志: {LOG_FILE}")


if __name__ == "__main__":
    main()
