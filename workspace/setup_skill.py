#!/usr/bin/env python3
"""
OpenCode Skill 安装和配置脚本
用于安装和管理 OpenCode 的各类技能（Skill）
"""

import os
import json
import subprocess
import time
import sys

# 日志配置
LOG_DIR = os.environ.get("LOG_DIR", "/dockerstartup/custom")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "setup_skill.log")

# =====================================
# OpenCode 路径配置 - 在 consol/debian-xfce-vnc 容器中
# =====================================
# consol/debian-xfce-vnc 容器中 root 用户的 HOME 是 /headless
ACTUAL_HOME = os.environ.get("ACTUAL_HOME", "/headless")
OPENCODE_HOME = os.environ.get("OPENCODE_HOME", os.path.join(ACTUAL_HOME, ".opencode"))
OPENCODE_CONFIG_DIR = os.environ.get("OPENCODE_CONFIG_DIR", os.path.join(ACTUAL_HOME, ".config", "opencode"))
OPENCODE_SKILLS_DIR = os.path.join(OPENCODE_HOME, "skills")
SKILLS_LIST_FILE = os.path.join(OPENCODE_HOME, "skills.json")

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

# Skill 清单
SKILLS = [
    "bestof",                          # 查找最佳实践与推荐
    "comparisons",                     # 对比不同市场或产品
    "studying",                        # 系统化学习与总结
    "flashcards",                      # 制作调研知识卡片
    "practice-test",                   # 测试调研知识掌握情况
    "generate-quiz",                   # 生成调研相关的练习题
    "shopping-savings",                # 价格与市场优惠趋势分析
    "genui",                           # 行业案例研究与分析
    "practice-test-orchestrator",      # 更复杂的测试与知识掌握情况
    "insert-backstory"                 # 背景研究与资料补充
]

# Skill 描述映射
SKILL_DESCRIPTIONS = {
    "bestof": "查找最佳实践与推荐",
    "comparisons": "对比不同市场或产品",
    "studying": "系统化学习与总结",
    "flashcards": "制作调研知识卡片",
    "practice-test": "测试调研知识掌握情况",
    "generate-quiz": "生成调研相关的练习题",
    "shopping-savings": "价格与市场优惠趋势分析",
    "genui": "行业案例研究与分析",
    "practice-test-orchestrator": "更复杂的测试与知识掌握情况",
    "insert-backstory": "背景研究与资料补充"
}

# 模块 1：准备 Skill 配置目录
def prepare_skill_dir():
    """创建 skill 配置目录"""
    os.makedirs(OPENCODE_SKILLS_DIR, exist_ok=True)
    log_message(f"Skill 目录已准备: {OPENCODE_SKILLS_DIR}")
    return OPENCODE_SKILLS_DIR

# 模块 2：写入 Skill 清单
def write_skill_list(skills):
    """写入 skill 清单到配置文件"""
    skill_config = {
        "skills": skills,
        "descriptions": SKILL_DESCRIPTIONS,
        "lastUpdated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(skills)
    }
    
    try:
        os.makedirs(os.path.dirname(SKILLS_LIST_FILE), exist_ok=True)
        with open(SKILLS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(skill_config, f, indent=2, ensure_ascii=False)
        log_message(f"Skill 清单已写入: {SKILLS_LIST_FILE}")
        return SKILLS_LIST_FILE
    except Exception as e:
        log_message(f"写入 Skill 清单失败: {e}", "ERROR")
        sys.exit(1)

# 模块 3：安装 Skill
def install_skills(skills):
    """使用 opencode 命令安装 skill"""
    log_message(f"开始安装 {len(skills)} 个 Skill...")
    
    if not command_exists("opencode"):
        log_message("opencode 命令不可用，请确保已安装 OpenCode", "ERROR")
        sys.exit(1)
    
    installed = []
    failed = []
    
    for idx, skill in enumerate(skills, 1):
        skill_display = f"{skill} ({SKILL_DESCRIPTIONS.get(skill, '无描述')})"
        log_message(f"[{idx}/{len(skills)}] 安装 Skill: {skill_display}")
        
        try:
            # 使用 opencode 命令安装 skill
            result = subprocess.run(
                ["opencode", "skill", "install", skill],
                capture_output=True,
                timeout=120,
                text=True
            )
            
            if result.returncode == 0:
                log_message(f"  ✅ {skill} 安装成功")
                installed.append(skill)
            else:
                error_msg = result.stderr or result.stdout
                log_message(f"  ⚠️ {skill} 安装失败: {error_msg}", "WARN")
                failed.append(skill)
                
        except subprocess.TimeoutExpired:
            log_message(f"  ⚠️ {skill} 安装超时 (120s)", "WARN")
            failed.append(skill)
        except Exception as e:
            log_message(f"  ⚠️ {skill} 安装出错: {e}", "WARN")
            failed.append(skill)
        
        time.sleep(1)  # 避免过快请求
    
    log_message(f"\n安装总结:")
    log_message(f"  成功: {len(installed)}/{len(skills)}")
    log_message(f"  失败: {len(failed)}/{len(skills)}")
    
    if failed:
        log_message(f"  失败的 Skill: {', '.join(failed)}", "WARN")
    
    return installed, failed

# 模块 4：检查 Skill 安装状态
def check_skills():
    """检查已安装的 skill"""
    log_message("检查已安装的 Skill...")
    
    if not command_exists("opencode"):
        log_message("opencode 命令不可用", "ERROR")
        return False
    
    try:
        result = subprocess.run(
            ["opencode", "skill", "list"],
            capture_output=True,
            timeout=30,
            text=True
        )
        
        if result.returncode == 0:
            output = result.stdout
            log_message("已安装的 Skill 列表:")
            for line in output.split('\n'):
                if line.strip():
                    log_message(f"  {line}")
            return True
        else:
            log_message("获取 Skill 列表失败", "WARN")
            return False
            
    except Exception as e:
        log_message(f"检查 Skill 失败: {e}", "WARN")
        return False

# 模块 5：自检 Skill 配置
def self_check_skills():
    """验证 skill 配置文件"""
    log_message("正在自检 Skill 配置...")
    
    if not os.path.exists(SKILLS_LIST_FILE):
        log_message(f"Skill 配置文件不存在: {SKILLS_LIST_FILE}", "WARN")
        return False
    
    try:
        with open(SKILLS_LIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if "skills" not in data or not isinstance(data["skills"], list):
            log_message("Skill 配置文件结构异常", "WARN")
            return False
        
        skills = data["skills"]
        log_message(f"✅ Skill 配置文件结构正确，共 {len(skills)} 个 Skill")
        
        if not skills:
            log_message("⚠️ 配置中没有任何 Skill", "WARN")
        else:
            log_message(f"Skill 清单 (最后更新: {data.get('lastUpdated', 'N/A')}):")
            for skill in skills:
                desc = data.get("descriptions", {}).get(skill, "无描述")
                log_message(f"  - {skill:<30} {desc}")
        
        return True
        
    except json.JSONDecodeError as e:
        log_message(f"JSON 解析失败: {e}", "ERROR")
        return False
    except Exception as e:
        log_message(f"自检失败: {e}", "ERROR")
        return False

# 模块 6：重启 WebUI（可选）
def restart_webui(restart=False):
    """重启 OpenCode WebUI 以应用新 Skill"""
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

# 辅助函数
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

# 主入口
def main():
    log_message("=" * 60)
    log_message("OpenCode Skill 安装和配置脚本")
    log_message("=" * 60)
    
    # 1. 准备目录
    prepare_skill_dir()
    
    # 2. 写入 Skill 清单
    write_skill_list(SKILLS)
    
    # 3. 自检配置
    if not self_check_skills():
        log_message("配置检查失败", "ERROR")
        sys.exit(1)
    
    # 4. 检查 OpenCode 是否已安装
    if not command_exists("opencode"):
        log_message("⚠️ OpenCode 未安装，跳过 Skill 安装步骤", "WARN")
        log_message("请先运行 init.sh 或手动安装 OpenCode")
    else:
        # 5. 安装 Skill
        installed, failed = install_skills(SKILLS)
        
        # 6. 检查已安装的 Skill
        check_skills()
        
        # 7. 可选：重启 WebUI 以应用新 Skill（默认不重启）
        # 如需重启，可以传入 restart=True
        restart_webui(restart=False)
    
    log_message("=" * 60)
    log_message("OpenCode Skill 配置完成")
    log_message("=" * 60)
    log_message(f"详细日志: {LOG_FILE}")

if __name__ == "__main__":
    main()
