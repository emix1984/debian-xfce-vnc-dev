import os
import json
import subprocess
import time
import sys

# 日志配置
LOG_DIR = os.environ.get("LOG_DIR", "/dockerstartup/custom")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "setup_mcp.log")

# =====================================
# OpenCode 路径配置 - 在 consol/debian-xfce-vnc 容器中
# =====================================
# consol/debian-xfce-vnc 容器中 root 用户的 HOME 是 /headless
ACTUAL_HOME = os.environ.get("ACTUAL_HOME", "/headless")
OPENCODE_HOME = os.environ.get("OPENCODE_HOME", os.path.join(ACTUAL_HOME, ".opencode"))
OPENCODE_CONFIG_DIR = os.environ.get("OPENCODE_CONFIG_DIR", os.path.join(ACTUAL_HOME, ".config", "opencode"))

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

# -------------------------------
# 模块 1：写入 MCP 配置
# -------------------------------
def write_config(mcp_config):
    config_dir = OPENCODE_CONFIG_DIR
    config_file = os.path.join(config_dir, "mcp.config.json")
    os.makedirs(config_dir, exist_ok=True)

    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(mcp_config, f, indent=2, ensure_ascii=False)
        log_message(f"MCP 配置已写入 {config_file}")
        return config_file
    except Exception as e:
        log_message(f"写入 MCP 配置失败: {e}", "ERROR")
        sys.exit(1)

# -------------------------------
# 模块 2：安装依赖
# -------------------------------
def install_dependencies():
    pip_packages = ["mem0ai", "playwright", "faiss-cpu", "sqlite-utils"]
    log_message("开始安装依赖...")

    for pkg in pip_packages:
        try:
            result = subprocess.run(["pip3", "install", "-q", pkg], check=True, capture_output=True)
            log_message(f"已安装 {pkg}")
        except subprocess.CalledProcessError as e:
            log_message(f"安装 {pkg} 失败: {e.stderr.decode('utf-8', errors='ignore')}", "WARN")
        except Exception as e:
            log_message(f"安装 {pkg} 出错: {e}", "WARN")

    try:
        result = subprocess.run(["playwright", "install", "--with-deps"], check=True, capture_output=True)
        log_message("Playwright 浏览器及系统依赖已安装")
    except subprocess.CalledProcessError as e:
        log_message(f"Playwright 驱动安装失败: {e.stderr.decode('utf-8', errors='ignore')}", "WARN")
    except Exception as e:
        log_message(f"Playwright 安装出错: {e}", "WARN")

# -------------------------------
def get_opencode_bin():
    """获取 opencode 可执行文件的路径，如果全局命令不在 PATH 中，则回退到绝对路径"""
    try:
        result = subprocess.run(["which", "opencode"], capture_output=True)
        if result.returncode == 0:
            return "opencode"
    except Exception:
        pass
    
    actual_home = os.environ.get("ACTUAL_HOME", "/headless")
    default_bin = os.path.join(actual_home, ".opencode", "bin", "opencode")
    if os.path.exists(default_bin):
        return default_bin
        
    return "opencode"

# -------------------------------
# 模块 3：重启 WebUI
# -------------------------------
def restart_webui():
    OPENCODE_PORT = 4096  # 与 init.sh 保持一致
    LOG_FILE_WEBUI = os.path.join(LOG_DIR, "opencode_web.log")
    
    log_message(f"正在重启 OpenCode WebUI (监听 0.0.0.0:{OPENCODE_PORT})...")
    
    # 停止现有进程
    try:
        result = subprocess.run(["pkill", "-f", "opencode web"], capture_output=True)
        log_message("已停止现有 OpenCode 进程")
        time.sleep(2)
    except Exception as e:
        log_message(f"停止进程时出错: {e}", "WARN")
    
    # 强制杀死仍然运行 of 进程
    try:
        subprocess.run(["pkill", "-9", "-f", "opencode web"], capture_output=True)
    except Exception:
        pass
    
    time.sleep(1)
    
    # 启动新实例
    opencode_bin = get_opencode_bin()
    try:
        cmd = f"nohup {opencode_bin} web --hostname 0.0.0.0 --port {OPENCODE_PORT} >> {LOG_FILE_WEBUI} 2>&1 &"
        subprocess.Popen(cmd, shell=True)
        log_message(f"已启动 OpenCode WebUI (PID 在后台运行)")
    except Exception as e:
        log_message(f"启动 OpenCode WebUI 失败: {e}", "ERROR")
        sys.exit(1)

# -------------------------------
# 模块 4：检测 WebUI 是否启动成功
# -------------------------------
def check_webui():
    OPENCODE_PORT = 4096
    CHECK_URL = f"http://127.0.0.1:{OPENCODE_PORT}"
    MAX_RETRIES = 10
    RETRY_INTERVAL = 3
    
    log_message(f"等待 WebUI 启动并检测... (最多等待 {MAX_RETRIES * RETRY_INTERVAL} 秒)")
    
    for attempt in range(MAX_RETRIES):
        try:
            result = subprocess.run(
                ["curl", "-s", "-m", "5", CHECK_URL],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                log_message(f"✅ WebUI 已成功启动并可访问 {CHECK_URL}")
                return True
        except Exception:
            pass
        
        if attempt < MAX_RETRIES - 1:
            log_message(f"尝试 {attempt + 1}/{MAX_RETRIES} 失败，{RETRY_INTERVAL} 秒后重试...")
            time.sleep(RETRY_INTERVAL)
    
    log_message(f"⚠️ WebUI 检测失败，请查看 {os.path.join(LOG_DIR, 'opencode_web.log')} 确认启动状态", "WARN")
    return False

# -------------------------------
# 模块 5：自检 MCP 配置是否妥当
# -------------------------------
def self_check(config_file):
    log_message("正在自检 MCP 配置...")
    
    if not os.path.exists(config_file):
        log_message(f"配置文件不存在: {config_file}", "ERROR")
        return False
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if "mcp" not in data or not isinstance(data["mcp"], dict):
            log_message("MCP 配置文件结构异常", "WARN")
            return False
        
        log_message("✅ MCP 配置文件结构正确")
        
        mcp_modules = data["mcp"]
        if not mcp_modules:
            log_message("⚠️ MCP 配置中没有任何模块", "WARN")
        else:
            log_message(f"已检测到 {len(mcp_modules)} 个 MCP 模块:")
            for key in mcp_modules.keys():
                log_message(f"  - {key}")
        
        return True
        
    except json.JSONDecodeError as e:
        log_message(f"JSON 解析失败: {e}", "ERROR")
        return False
    except Exception as e:
        log_message(f"自检失败: {e}", "ERROR")
        return False

# -------------------------------
# 主入口
# -------------------------------
def main():
    log_message("=" * 50)
    log_message("开始配置 OpenCode MCP")
    log_message("=" * 50)
    
    mcp_config = {
        "mcp": {
            "searxng": {"base_url": "http://localhost:8080"},
            "dcp": {"max_tokens": 4000, "strategy": "semantic"},
            "mem0": {"storage": "sqlite:///mem0.db"},
            "browser": {"engine": "playwright", "headless": True},
            "local_embedding": {"storage": "faiss_index"},
            "local_llm": {"engine": "ollama", "model": "qwen2.5-coder:32b"},
            "filesystem": {"root_path": "/headless/Desktop/workspace"},
            "shell": {"safe_mode": True},
            "pdf_parser": {"storage": "parsed_docs"},
            "sqlite": {"db_path": "local_data.db"}
        }
    }

    config_file = write_config(mcp_config)
    
    if not self_check(config_file):
        log_message("配置检查失败", "ERROR")
        sys.exit(1)
    
    install_dependencies()
    restart_webui()
    check_webui()
    
    log_message("=" * 50)
    log_message("OpenCode MCP 配置完成")
    log_message("=" * 50)

if __name__ == "__main__":
    main()
