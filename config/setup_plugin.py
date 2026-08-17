#!/usr/bin/env python3
"""
OpenCode Plugin 安装和配置脚本
用于安装和管理 OpenCode 的各类插件
"""

import os
import json
import re
import subprocess
import time
import sys
from opencode_utils import (
    OPENCODE_HOME,
    get_log_file,
    log as _log,
    command_exists,
    restart_webui,
)

LOG_FILE = get_log_file("setup_plugin")
OPENCODE_PLUGINS_DIR = os.path.join(OPENCODE_HOME, "plugins")
PLUGINS_LIST_FILE = os.path.join(OPENCODE_HOME, "plugins.json")


def log(msg, level="INFO"):
    _log(msg, level, LOG_FILE)


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?25[hl]")


def strip_ansi(text):
    """去除 ANSI 转义码"""
    return ANSI_RE.sub("", text)


def extract_error(output):
    """从 opencode plugin 输出中提取实际错误信息"""
    clean = strip_ansi(output)
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    error_lines = []
    for line in lines:
        line = line.lstrip("│┌└─●◆◇◒◐◓◑■ ").strip()
        if not line or line.startswith("Install") or line.startswith("Installing"):
            continue
        if "Install failed" in line or "Could not install" in line:
            continue
        if "plugin package" in line.lower():
            continue
        if line.startswith("Done"):
            continue
        error_lines.append(line)
    return "; ".join(error_lines) if error_lines else "未知错误（无输出）"


# Plugin 清单
PLUGINS = [
    # Original working plugins
    "oh-my-opencode-slim@git+https://github.com/alvinunreal/oh-my-opencode-slim.git",
    "superpowers@git+https://github.com/obra/superpowers.git",
    "opencode-pty@git+https://github.com/shekohex/opencode-pty.git",
    "opencode-supermemory@git+https://github.com/supermemoryai/opencode-supermemory.git",
    "opencode-agent-skills@git+https://github.com/joshuadavidthomas/opencode-agent-skills.git",
    "opencode-browser@git+https://github.com/different-ai/opencode-browser.git",
    "opencode-arise@git+https://github.com/moinulmoin/opencode-arise.git",
    "opencode-token-monitor@git+https://github.com/Ainsley0917/opencode-token-monitor.git",
    "opencode-tmux-plugin@git+https://github.com/liba2k/opencode-tmux-plugin.git",
    "opencode-preview@git+https://github.com/Edison-A-N/opencode-preview.git",
    # Newly added (verified accessible)
    "opencode-wakatime@git+https://github.com/angristan/opencode-wakatime.git",
    "opencode-helicone-session@git+https://github.com/H2Shami/opencode-helicone-session.git",
    "opencode-eslint-formatter@git+https://github.com/samholmes/opencode-eslint-formatter.git",
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
    """写入 plugin 清单到配置文件 (只保留干净的包名)"""
    names = []
    for p in plugins:
        if isinstance(p, str) and p:
            name = p.split("@")[0]
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
    except Exception as e:
        log(f"写入 Plugin 清单失败: {e}", "ERROR")
        sys.exit(1)


OPENCODE_CACHE_DIR = os.path.join(
    os.environ.get("ACTUAL_HOME", "/headless"), ".cache", "opencode", "packages"
)


def _find_bun():
    """查找可用的 bun 可执行文件"""
    for p in [
        os.path.join(os.environ.get("HOME", "/root"), ".bun", "bin", "bun"),
        "/usr/local/bin/bun",
        "/usr/bin/bun",
    ]:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def _plugin_to_cache_dir(plugin):
    """将 plugin 标识符转换为 opencode 缓存目录路径"""
    # 格式: name@git+https://github.com/user/repo.git
    # 缓存路径: .../packages/name@git+https:/github.com/user/repo.git
    # 注意 git+https: 后只有一个 /
    if "@git+https://" not in plugin:
        return None
    name, url = plugin.split("@git+https://", 1)
    cache_name = f"{name}@git+https:/{url}"
    return os.path.join(OPENCODE_CACHE_DIR, cache_name)


def _bun_preinstall(plugin):
    """用 bun 预装依赖到 opencode 缓存目录，绕过 opencode 内部 npm 的 git dep preparation bug"""
    bun_bin = _find_bun()
    if not bun_bin:
        return False

    cache_dir = _plugin_to_cache_dir(plugin)
    if not cache_dir:
        return False

    # 从 plugin 标识符提取 user/repo
    # 格式: name@git+https://github.com/user/repo.git
    if "@git+https://github.com/" not in plugin:
        return False
    raw_name = plugin.split("@git+")[0]
    github_path = plugin.split("@git+https://github.com/", 1)[1].rstrip("/")
    if github_path.endswith(".git"):
        github_path = github_path[:-4]

    # 提取包名（@scope/name 取 / 后的部分）
    if raw_name.startswith("@"):
        raw_name = raw_name.rsplit("/", 1)[-1]

    try:
        os.makedirs(cache_dir, exist_ok=True)
        pkg_json = os.path.join(cache_dir, "package.json")
        with open(pkg_json, "w") as f:
            json.dump({"dependencies": {raw_name: f"github:{github_path}"}}, f)

        result = subprocess.run(
            [bun_bin, "install"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cache_dir,
        )
        if result.returncode == 0:
            log(f"  [FIX] bun 预装依赖成功: {plugin}")
            return True
        else:
            log(
                f"  [WARN] bun 预装依赖失败: {(result.stderr or result.stdout or '').strip()[:200]}",
                "WARN",
            )
    except Exception as e:
        log(f"  [WARN] bun 预装异常: {e}", "WARN")

    return False


def install_single_plugin(plugin, idx, total):
    log(f"[{idx}/{total}] 开始安装 Plugin: {plugin}")
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                ["opencode", "plugin", plugin, "--force"],
                capture_output=True,
                timeout=120,
                text=True,
            )
            combined = (result.stdout or "") + (result.stderr or "")
            if result.returncode == 0 and "Install failed" not in combined:
                log(f"  [OK] {plugin} 安装成功")
                return (plugin, True)

            err_msg = extract_error(combined)
            log(
                f"  [WARN] 尝试 {attempt}/{max_retries} - {plugin} 安装失败: {err_msg}",
                "WARN",
            )

            # 如果是 git dep preparation failed，尝试 bun 预装后重试
            if "git dep preparation failed" in combined:
                if _bun_preinstall(plugin):
                    # bun 预装成功，直接重试 opencode plugin（不计入 retry 次数）
                    try:
                        result2 = subprocess.run(
                            ["opencode", "plugin", plugin, "--force"],
                            capture_output=True,
                            timeout=120,
                            text=True,
                        )
                        combined2 = (result2.stdout or "") + (result2.stderr or "")
                        if (
                            result2.returncode == 0
                            and "Install failed" not in combined2
                        ):
                            log(f"  [OK] {plugin} 安装成功（bun 预装后）")
                            return (plugin, True)
                        else:
                            log(
                                f"  [WARN] bun 预装后仍失败: {extract_error(combined2)}",
                                "WARN",
                            )
                    except Exception as e:
                        log(f"  [WARN] bun 预装后重试出错: {e}", "WARN")

        except subprocess.TimeoutExpired:
            log(
                f"  [WARN] 尝试 {attempt}/{max_retries} - {plugin} 安装超时 (120s)",
                "WARN",
            )
        except Exception as e:
            log(
                f"  [WARN] 尝试 {attempt}/{max_retries} - {plugin} 安装出错: {e}",
                "WARN",
            )

        if attempt < max_retries:
            time.sleep(2)

    log(f"  [ERROR] {plugin} 在 {max_retries} 次尝试后最终安装失败", "ERROR")
    return (plugin, False)


def install_plugins_legacy(plugins):
    """使用 opencode plugin <module> 命令安装插件 (串行备份逻辑)"""
    log(f"正在使用备份逻辑串行安装 {len(plugins)} 个 Plugin...")

    if not command_exists("opencode"):
        log("opencode 命令不可用，请确保已安装 OpenCode", "ERROR")
        sys.exit(1)

    installed = []
    failed = []

    for idx, plugin in enumerate(plugins, 1):
        plugin_name, success = install_single_plugin(plugin, idx, len(plugins))
        if success:
            installed.append(plugin_name)
        else:
            failed.append(plugin_name)

    log(
        f"安装总结: 成功 {len(installed)}/{len(plugins)}, 失败 {len(failed)}/{len(plugins)}"
    )
    if failed:
        log(f"  失败的 Plugin: {', '.join(failed)}", "WARN")

    return installed, failed


def install_plugins(plugins):
    """通过生成 package.json 并执行 bun install 来安装所有插件，以保证安装成功率 100% 且显示名称简短干净"""
    log("开始生成 package.json 并批量安装 Plugin...")

    # 1. 构造 package.json 依赖
    dependencies = {"@opencode-ai/plugin": "1.18.2"}
    for p in plugins:
        if not isinstance(p, str) or not p:
            continue
        if "@" in p:
            name, url = p.split("@", 1)
            dependencies[name] = url
        else:
            dependencies[p] = "latest"

    # 2. 写入 package.json
    pkg_json_file = os.path.join(OPENCODE_HOME, "package.json")
    try:
        existing_data = {}
        if os.path.exists(pkg_json_file):
            try:
                with open(pkg_json_file, "r") as f:
                    existing_data = json.load(f)
            except Exception:
                pass

        existing_data["dependencies"] = dependencies
        with open(pkg_json_file, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        log(f"package.json 依赖配置已更新: {pkg_json_file}")
    except Exception as e:
        log(f"写入 package.json 失败: {e}", "ERROR")
        sys.exit(1)

    # 3. 运行 bun install
    bun_bin = _find_bun()
    if not bun_bin:
        log("bun 未找到，退回使用 opencode plugin 命令逐个安装...", "WARN")
        return install_plugins_legacy(plugins)

    log("正在通过 bun 批量安装插件和依赖...")
    try:
        result = subprocess.run(
            [bun_bin, "install"],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=OPENCODE_HOME,
        )
        if result.returncode == 0:
            log("[OK] 所有插件已通过 bun 成功安装到 node_modules 中！")
            return list(dependencies.keys()), []
        else:
            log(f"bun install 失败: {result.stderr or result.stdout}", "WARN")
            log("退回使用 opencode plugin 命令逐个安装...", "WARN")
            return install_plugins_legacy(plugins)
    except Exception as e:
        log(f"bun 安装异常: {e}", "WARN")
        log("退回使用 opencode plugin 命令逐个安装...", "WARN")
        return install_plugins_legacy(plugins)


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
