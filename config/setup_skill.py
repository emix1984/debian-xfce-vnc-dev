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
from opencode_utils import (
    OPENCODE_HOME,
    get_log_file,
    log as _log,
    command_exists,
    restart_webui,
)

LOG_FILE = get_log_file("setup_skill")
OPENCODE_SKILLS_DIR = os.path.join(OPENCODE_HOME, "skills")
SKILLS_LIST_FILE = os.path.join(OPENCODE_HOME, "skills.json")


def log(msg, level="INFO"):
    _log(msg, level, LOG_FILE)


# 优化后的 Skill 清单 (精简至 12 个核心技能，按领域分组)
SKILLS = [
    # --- 开发与架构类 ---
    "karpathy-guidelines",
    "fullstack-agent-suite",
    "frontend-artifacts-builder",
    # --- 审查与测试类 ---
    "code-review-workflow",
    "code-review-graph",
    "webapp-testing",
    # --- 学习与评估类 ---
    "learning-and-research",
    "practice-assessment",
    "flashcards",
    "agent-browser",
    # --- 商业调研与分析类 ---
    "industry-case-analysis",
    "market-comparison",
    "shopping-savings",
    # --- 搜索与扩展技能 ---
    "anysearch-skill@git+https://github.com/anysearch-ai/anysearch-skill.git",
    "nuwa-skill@git+https://github.com/alchaincyf/nuwa-skill.git",
    "darwin-skill@git+https://github.com/alchaincyf/darwin-skill.git",
    "agent-reach@git+https://github.com/Panniantong/agent-reach.git",
    "ponytail@git+https://github.com/DietrichGebert/ponytail.git",
]

# 优化后的 Skill 描述映射
SKILL_DESCRIPTIONS = {
    # 开发与架构类
    "karpathy-guidelines": "Karpathy 编程思维与规范",
    "fullstack-agent-suite": "综合全栈开发技能套件 (涵盖前后端 API 构建、容器化部署与服务器配置)",
    "frontend-artifacts-builder": "生成复杂 HTML 构件与生产级前端 UI 设计",
    # 审查与测试类
    "code-review-workflow": "跨语言 (包含 Python/HTML 等) 的代码、安全与架构设计审查工作流",
    "code-review-graph": "代码知识图谱与项目结构分析",
    "webapp-testing": "Playwright 前端与自动化测试",
    # 学习与评估类
    "learning-and-research": "系统化学习、背景资料提取与深度调研总结",
    "practice-assessment": "生成练习题并执行从基础到复杂的知识掌握情况综合评估",
    "flashcards": "提取核心概念，制作调研与学习知识卡片",
    "agent-browser": "agent-browser 浏览器自动化及 MCP 集成能力",
    # 商业调研与分析类
    "industry-case-analysis": "行业案例研究分析与商业应用洞察",
    "market-comparison": "对比不同区域市场与竞品，并提炼最佳实践与策略推荐",
    "shopping-savings": "产品价格追踪、平台政策与物流成本趋势分析",
    # 搜索与扩展技能
    "anysearch-skill@git+https://github.com/anysearch-ai/anysearch-skill.git": "AnySearch AI 搜索与增强辅助技能",
    "nuwa-skill@git+https://github.com/alchaincyf/nuwa-skill.git": "Nuwa Skill 拓展能力",
    "darwin-skill@git+https://github.com/alchaincyf/darwin-skill.git": "Darwin Skill 拓展能力",
    "agent-reach@git+https://github.com/Panniantong/agent-reach.git": "Agent Reach 触达功能",
    "ponytail@git+https://github.com/DietrichGebert/ponytail.git": "Ponytail 开发工具辅助",
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
        log(f"[OK] Skill 配置文件结构正确，共 {len(skills)} 个 Skill")

        if not skills:
            log("[WARN] 配置中没有任何 Skill", "WARN")
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
        log("[OK] OpenCode 已安装，Skill 配置将在 OpenCode 启动后自动加载")
    else:
        log("[WARN] OpenCode 未安装，请先运行 container-init.sh 安装 OpenCode", "WARN")

    # 5. 可选：重启 WebUI（默认不重启）
    do_restart_webui(restart=False)

    log("=" * 60)
    log("OpenCode Skill 配置完成")
    log("=" * 60)
    log(f"详细日志: {LOG_FILE}")


if __name__ == "__main__":
    main()
