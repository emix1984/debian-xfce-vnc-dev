"""
Shared utilities for OpenCode setup scripts (plugins, skills, etc.)
"""
import os
import time
import subprocess

# =====================================
# OpenCode Path Setup
# =====================================
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTUAL_HOME = os.environ.get("ACTUAL_HOME", "/headless")
OPENCODE_HOME = os.environ.get("OPENCODE_HOME", os.path.join(ACTUAL_HOME, ".opencode"))
OPENCODE_CONFIG_DIR = os.environ.get("OPENCODE_CONFIG_DIR", os.path.join(ACTUAL_HOME, ".config", "opencode"))

# Update PATH
os.environ["PATH"] = os.path.join(OPENCODE_HOME, "bin") + ":" + os.environ.get("PATH", "")

# Log Directory
LOG_DIR = os.environ.get("LOG_DIR", "/dockerstartup/custom")
os.makedirs(LOG_DIR, exist_ok=True)

def get_log_file(script_name: str) -> str:
    return os.path.join(LOG_DIR, f"{script_name}.log")

def log(msg, level="INFO", log_file=None):
    """Log to stdout and append to the specified log file."""
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}"
    print(line)
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

def command_exists(cmd):
    """Check if command exists in PATH"""
    try:
        r = subprocess.run(["which", cmd], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False

def restart_webui(restart=False, log_func=None):
    """Restart OpenCode WebUI (optional)"""
    if not log_func:
        log_func = lambda msg, level="INFO": print(msg)

    if not restart:
        log_func("跳过 WebUI 重启（可选）")
        return

    port = 4096
    webui_log = os.path.join(LOG_DIR, "opencode_web.log")

    log_func("正在重启 OpenCode WebUI...")

    subprocess.run(["pkill", "-f", "opencode web"], capture_output=True)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", "opencode web"], capture_output=True)
    time.sleep(1)

    try:
        cmd = f"nohup opencode web --hostname 0.0.0.0 --port {port} >> {webui_log} 2>&1 &"
        subprocess.Popen(cmd, shell=True)
        log_func(f"[OK] OpenCode WebUI 已重启 (端口 {port})")
    except Exception as e:
        log_func(f"启动 OpenCode WebUI 失败: {e}", "ERROR")
