#!/usr/bin/env python3
"""
OpenCode Skill 安装和配置脚本
用于安装和管理 OpenCode 的各类技能（Skill）

注意: opencode CLI 没有 skill 子命令，所以 Skill 只能通过写入配置文件来注册。
本脚本负责：
  1. 创建 skill 目录
  2. 写入 skill 清单到 JSON 配置
  3. 自检配置是否正确
"""

import os
import json
import subprocess
import time
import sys

# =====================================
# OpenCode 路径配置 - 在 consol/debian-xfce-vnc 容器中
# =====================================
ACTUAL_HOME = os.environ.get("ACTUAL_HOME", "/headless")
OPENCODE_HOME = os.environ.get("OPENCODE_HOME", os.path.join(ACTUAL_HOME, ".opencode"))
OPENCODE_CONFIG_DIR = os.environ.get("OPENCODE_CONFIG_DIR", os.path.join(ACTUAL_HOME, ".config", "opencode"))
OPENCODE_SKILLS_DIR = os.path.join(OPENCODE_HOME, "skills")
SKILLS_LIST_FILE = os.path.join(OPENCODE_HOME, "skills.json")

# 将 OpenCode 的 bin 目录加入 PATH
os.environ["PATH"] = os.path.join(OPENCODE_HOME, "bin") + ":" + os.environ.get("PATH", "")

# 日志配置 - 日志文件固定存放在 /dockerstartup/custom
LOG_DIR = os.environ.get("LOG_DIR", "/dockerstartup/custom")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "setup_skill.log")


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


# Skill 清单
SKILLS = [
    "bestof",
    "comparisons",
    "studying",
    "flashcards",
    "practice-test",
    "generate-quiz",
    "shopping-savings",
    "genui",
    "practice-test-orchestrator",
    "insert-backstory",
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
    "insert-backstory": "背景研究与资料补充",
}


# -------------------------------
# 模块 1：准备 Skill 配置目录
# -------------------------------
def prepare_skill_dir():
    """创建 skill 配置目录"""
    os.makedirs(OPENCODE_SKILLS_DIR, exist_ok=True)
    log(f"Skill 目录已准备: {OPENCODE_SKILLS_DIR}")


# -------------------------------
# 模块 2：写入 Skill 清单
# -------------------------------
def write_skill_list(skills):
    """写入 skill 清单到配置文件"""
    data = {
        "skills": skills,
        "descriptions": SKILL_DESCRIPTIONS,
        "lastUpdated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(skills),
    }
    try:
        os.makedirs(os.path.dirname(SKILLS_LIST_FILE), exist_ok=True)
        with open(SKILLS_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"Skill 清单已写入: {SKILLS_LIST_FILE}")
    except Exception as e:
        log(f"写入 Skill 清单失败: {e}", "ERROR")
        sys.exit(1)


# -------------------------------
# 模块 3：自检 Skill 配置
# -------------------------------
def self_check():
    """验证 skill 配置文件"""
    log("正在自检 Skill 配置...")

    if not os.path.exists(SKILLS_LIST_FILE):
        log(f"Skill 配置文件不存在: {SKILLS_LIST_FILE}", "WARN")
        return False

    try:
        with open(SKILLS_LIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "skills" not in data or not isinstance(data["skills"], list):
            log("Skill 配置文件结构异常", "WARN")
            return False

        skills = data["skills"]
        log(f"✅ Skill 配置文件结构正确，共 {len(skills)} 个 Skill")

        if not skills:
            log("⚠️ 配置中没有任何 Skill", "WARN")
        else:
            log(f"Skill 清单 (最后更新: {data.get('lastUpdated', 'N/A')}):")
            for s in skills:
                desc = data.get("descriptions", {}).get(s, "无描述")
                log(f"  - {s:<30} {desc}")

        return True

    except json.JSONDecodeError as e:
        log(f"JSON 解析失败: {e}", "ERROR")
        return False
    except Exception as e:
        log(f"自检失败: {e}", "ERROR")
        return False


# -------------------------------
# 模块 4：重启 WebUI（可选）
# -------------------------------
def restart_webui(restart=False):
    """重启 OpenCode WebUI 以应用新 Skill"""
    if not restart:
        log("跳过 WebUI 重启（可选）")
        return

    port = 4096
    webui_log = os.path.join(LOG_DIR, "opencode_web.log")

    log("正在重启 OpenCode WebUI...")

    subprocess.run(["pkill", "-f", "opencode web"], capture_output=True)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", "opencode web"], capture_output=True)
    time.sleep(1)

    try:
        cmd = f"nohup opencode web --hostname 0.0.0.0 --port {port} >> {webui_log} 2>&1 &"
        subprocess.Popen(cmd, shell=True)
        log(f"✅ OpenCode WebUI 已重启 (端口 {port})")
    except Exception as e:
        log(f"启动 OpenCode WebUI 失败: {e}", "ERROR")


# -------------------------------
# 主入口
# -------------------------------
def main():
    log("=" * 60)
    log("OpenCode Skill 安装和配置脚本")
    log("=" * 60)

    # 1. 准备目录
    prepare_skill_dir()

    # 2. 写入 Skill 清单
    write_skill_list(SKILLS)

    # 3. 自检配置
    if not self_check():
        log("配置检查失败", "ERROR")
        sys.exit(1)

    # 4. 提示信息
    #    opencode CLI 没有 skill 子命令，所以无法通过命令行安装 Skill
    #    Skill 配置文件已写入，OpenCode 启动后会自动加载
    if command_exists("opencode"):
        log("✅ OpenCode 已安装，Skill 配置将在 OpenCode 启动后自动加载")
    else:
        log("⚠️ OpenCode 未安装，请先运行 init.sh 安装 OpenCode", "WARN")

    # 5. 可选：重启 WebUI（默认不重启）
    restart_webui(restart=False)

    log("=" * 60)
    log("OpenCode Skill 配置完成")
    log("=" * 60)
    log(f"详细日志: {LOG_FILE}")


if __name__ == "__main__":
    main()
