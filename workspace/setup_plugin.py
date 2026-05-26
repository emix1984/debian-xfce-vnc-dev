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

# 日志配置
LOG_DIR = os.environ.get("LOG_DIR", "/dockerstartup/custom")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "setup_plugin.log")

# =====================================
# OpenCode 路径配置 - 在 consol/debian-xfce-vnc 容器中
# =====================================
# consol/debian-xfce-vnc 容器中 root 用户的 HOME 是 /headless
ACTUAL_HOME = os.environ.get("ACTUAL_HOME", "/headless")
OPENCODE_HOME = os.environ.get("OPENCODE_HOME", os.path.join(ACTUAL_HOME, ".opencode"))
OPENCODE_CONFIG_DIR = os.environ.get("OPENCODE_CONFIG_DIR", os.path.join(ACTUAL_HOME, ".config", "opencode"))
OPENCODE_PLUGINS_DIR = os.path.join(OPENCODE_HOME, "plugins")
PLUGINS_LIST_FILE = os.path.join(OPENCODE_HOME, "plugins.json")

def log_message(msg, level="INFO"):
    """记录日志消息"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {msg}"
    print(log_line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception as e:
        print(f"⚠️ 日志写入失败: {e}")

# Plugin 清单
PLUGINS = [
    "oh-my-opencode-slim",
    "superpowers@git+https://github.com/obra/superpowers.git",
    "opencode-pty",
    "opencode-supermemory",
    "@morphllm/opencode-morph-plugin",
    "opencode-agent-skills",
    "opencode-worktree",
    "opencode-type-inject",
    "opencode-browser",
    "opencode-arise",
    "opencode-token-monitor"
]

# 配置路径
OPENCODE_HOME = os.path.join(os.path.expanduser("~"), ".opencode")
PLUGINS_CONFIG_DIR = os.path.join(OPENCODE_HOME, "plugins")
PLUGINS_LIST_FILE = os.path.join(OPENCODE_HOME, "plugins.json")

# -------------------------------
# 模块 1：准备 Plugin 配置目录
# -------------------------------
def prepare_plugin_dir():
    """创建 plugin 配置目录"""
    os.makedirs(OPENCODE_PLUGINS_DIR, exist_ok=True)
    log_message(f"Plugin 目录已准备: {OPENCODE_PLUGINS_DIR}")
    return OPENCODE_PLUGINS_DIR

# -------------------------------
# 模块 2：写入 Plugin 清单
# -------------------------------
def write_plugin_list(plugins):
    """写入 plugin 清单到配置文件"""
    # 过滤非字符串或空值，防止出现意外的 'list' 占位符
    cleaned_plugins = [p for p in plugins if isinstance(p, str) and p]
    plugin_config = {
        "plugins": cleaned_plugins,
        "lastUpdated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(cleaned_plugins)
    }
    
    try:
        os.makedirs(os.path.dirname(PLUGINS_LIST_FILE), exist_ok=True)
        with open(PLUGINS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(plugin_config, f, indent=2, ensure_ascii=False)
        log_message(f"Plugin 清单已写入: {PLUGINS_LIST_FILE}")
        return PLUGINS_LIST_FILE
    except Exception as e:
        log_message(f"写入 Plugin 清单失败: {e}", "ERROR")
        sys.exit(1)

# -------------------------------
# 模块 3：安装 Plugin
# -------------------------------
def install_plugins(plugins):
    """使用 opencode 命令安装 plugin"""
    log_message(f"开始安装 {len(plugins)} 个 Plugin...")
    
    if not command_exists("opencode"):
        log_message("opencode 命令不可用，请确保已安装 OpenCode", "ERROR")
        sys.exit(1)
    
    installed = []
    failed = []
    
    for idx, plugin in enumerate(plugins, 1):
        log_message(f"[{idx}/{len(plugins)}] 安装 Plugin: {plugin}")
        
        try:
            # 使用 npm install 或 opencode 命令安装
            result = subprocess.run(
                ["opencode", "plugin", "install", plugin],
                capture_output=True,
                timeout=120,
                text=True
            )
            
            if result.returncode == 0:
                log_message(f"  ✅ {plugin} 安装成功")
                installed.append(plugin)
            else:
                error_msg = result.stderr or result.stdout
                log_message(f"  ⚠️ {plugin} 安装失败: {error_msg}", "WARN")
                failed.append(plugin)
                
        except subprocess.TimeoutExpired:
            log_message(f"  ⚠️ {plugin} 安装超时 (120s)", "WARN")
            failed.append(plugin)
        except Exception as e:
            log_message(f"  ⚠️ {plugin} 安装出错: {e}", "WARN")
            failed.append(plugin)
        
        time.sleep(1)  # 避免过快请求
    
    log_message(f"\n安装总结:")
    log_message(f"  成功: {len(installed)}/{len(plugins)}")
    log_message(f"  失败: {len(failed)}/{len(plugins)}")
    
    if failed:
        log_message(f"  失败的 Plugin: {', '.join(failed)}", "WARN")
    
    return installed, failed

# -------------------------------
# 模块 4：检查 Plugin 安装状态
# -------------------------------
def check_plugins():
    """检查已安装的 plugin"""
    log_message("检查已安装的 Plugin...")
    
    if not os.path.exists(PLUGINS_LIST_FILE):
        log_message(f"未找到插件配置文件: {PLUGINS_LIST_FILE}", "WARN")
        return False
        
    try:
        with open(PLUGINS_LIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        plugins = data.get("plugins", [])
        log_message("已配置的插件列表 (自检通过):")
        for plugin in plugins:
            log_message(f"  - {plugin}")
        return True
    except Exception as e:
        log_message(f"自检读取 Plugin 列表失败: {e}", "WARN")
        return False

# -------------------------------
# 模块 5：自检 Plugin 配置
# -------------------------------
def self_check_plugins():
    """验证 plugin 配置文件"""
    log_message("正在自检 Plugin 配置...")
    
    if not os.path.exists(PLUGINS_LIST_FILE):
        log_message(f"Plugin 配置文件不存在: {PLUGINS_LIST_FILE}", "WARN")
        return False
    
    try:
        with open(PLUGINS_LIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 若结构异常（如出现字符串 "list"），尝试自动修复为合法列表
        if isinstance(data.get("plugins"), list):
            plugins = [p for p in data["plugins"] if isinstance(p, str) and p != "list"]
            data["plugins"] = plugins
        else:
            data["plugins"] = []
        # 将修复后的结构写回文件
        try:
            with open(PLUGINS_LIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log_message("已修复 Plugin 配置文件结构")
        except Exception as e:
            log_message(f"修复配置文件失败: {e}", "WARN")
        plugins = data["plugins"]
        
        plugins = data["plugins"]
        log_message(f"✅ Plugin 配置文件结构正确，共 {len(plugins)} 个 Plugin")
        
        if not plugins:
            log_message("⚠️ 配置中没有任何 Plugin", "WARN")
        else:
            log_message(f"Plugin 清单 (最后更新: {data.get('lastUpdated', 'N/A')}):")
            for plugin in plugins:
                log_message(f"  - {plugin}")
        
        return True
        
    except json.JSONDecodeError as e:
        log_message(f"JSON 解析失败: {e}", "ERROR")
        return False
    except Exception as e:
        log_message(f"自检失败: {e}", "ERROR")
        return False

# -------------------------------
# 模块 6：重启 WebUI（可选）
# -------------------------------
def restart_webui(restart=False):
    """重启 OpenCode WebUI 以应用新 Plugin"""
    if not restart:
        log_message("跳过 WebUI 重启（可选）")
        return
    
    OPENCODE_PORT = 4096
    LOG_FILE_WEBUI = os.path.join(LOG_DIR, "opencode_web.log")
    
    log_message(f"正在重启 OpenCode WebUI...")
    
    # 停止现有进程
    try:
        subprocess.run(["pkill", "-f", "opencode web"], capture_output=True)
        log_message("已停止现有 OpenCode 进程")
        time.sleep(2)
    except Exception as e:
        log_message(f"停止进程时出错: {e}", "WARN")
    
    # 强制杀死仍然运行的进程
    try:
        subprocess.run(["pkill", "-9", "-f", "opencode web"], capture_output=True)
    except Exception:
        pass
    
    time.sleep(1)
    
    # 启动新实例
    try:
        cmd = f"nohup opencode web --hostname 0.0.0.0 --port {OPENCODE_PORT} >> {LOG_FILE_WEBUI} 2>&1 &"
        subprocess.Popen(cmd, shell=True)
        log_message(f"✅ OpenCode WebUI 已重启 (PID 在后台运行)")
    except Exception as e:
        log_message(f"启动 OpenCode WebUI 失败: {e}", "ERROR")

# -------------------------------
# 辅助函数
# -------------------------------
def command_exists(cmd):
    """检查命令是否存在"""
    try:
        result = subprocess.run(
            ["which", cmd],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

# -------------------------------
# 主入口
# -------------------------------
def main():
    log_message("=" * 60)
    log_message("OpenCode Plugin 安装和配置脚本")
    log_message("=" * 60)
    
    # 1. 准备目录
    prepare_plugin_dir()
    
    # 2. 写入 Plugin 清单
    write_plugin_list(PLUGINS)
    
    # 3. 自检配置
    if not self_check_plugins():
        log_message("配置检查失败", "ERROR")
        sys.exit(1)
    
    # 4. 检查 OpenCode 是否已安装
    if not command_exists("opencode"):
        log_message("⚠️ OpenCode 未安装，跳过 Plugin 安装步骤", "WARN")
        log_message("请先运行 init.sh 或手动安装 OpenCode")
    else:
        # 5. 安装 Plugin
        installed, failed = install_plugins(PLUGINS)
        
        # 6. 检查已安装的 Plugin
        check_plugins()
        
        # 7. 可选：重启 WebUI 以应用新 Plugin（默认不重启）
        # 如需重启，可以传入 restart=True
        restart_webui(restart=False)
    
    log_message("=" * 60)
    log_message("OpenCode Plugin 配置完成")
    log_message("=" * 60)
    log_message(f"详细日志: {LOG_FILE}")

if __name__ == "__main__":
    main()
