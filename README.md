# Debian Xfce VNC 智能开发与 Agent 工作站

基于 [consol/debian-xfce-vnc](https://github.com/ConSol/docker-headless-vnc-container) 官方镜像，通过 `docker-compose.yml` + `init.sh` 构建的免编译、即插即用型 AI Agent 开发与测试沙盒环境。

本工作站已深度集成 **OpenCode**（一款先进的本地开发与智能体执行框架），并配备了完善的 MCP（Model Context Protocol）能力配置脚本、远程 LLM（Ollama）智能对接方案，以及自动化插件与技能分发体系。

---

## 目录结构

```text
debian-xfce-vnc-dev/
├── docker-compose.yml          # 容器编排 — 配置宿主机端口映射、目录挂载及系统变量
├── init.sh                     # 容器初次启动引导脚本 — 初始化用户、配置SSH服务、安装系统依赖及OpenCode
├── README.md                   # 本说明文件
└── workspace/                  # 专用工作空间（挂载至容器桌面 `/headless/Desktop/workspace`）
    ├── setup_mcp.py            # MCP 依赖及配置安装脚本（含 mem0ai、Playwright、FAISS 等）
    ├── setup_opencode_ollama.sh# 远程 Ollama 实例连接与模型智能导入脚本
    ├── setup_plugin.py         # OpenCode 插件管理与自动安装工具
    ├── setup_skill.py          # OpenCode 技能包管理与自动安装工具
    └── restart_opencode.sh     # OpenCode Web 服务一键热重启工具
```

---

## 访问与服务端口

容器启动后，将对外暴露以下通信与管理接口：

| 服务 | 宿主机映射地址 | 容器内部端口 | 说明 |
| :--- | :--- | :--- | :--- |
| **VNC 桌面** | `vnc://localhost:5901` | `5901` | 使用 VNC Viewer 等客户端直接访问系统桌面 |
| **noVNC 网页版** | `http://localhost:6901` | `6901` | 浏览器直接访问的桌面终端，适合无客户端环境 |
| **SSH 服务** | `ssh default@localhost -p 2222` | `22` | 宿主机终端命令行远程登录容器（默认用户 `default`） |
| **OpenCode WebUI**| `http://localhost:4096` | `4096` | OpenCode 内置开发者 Web 交互与控制界面 |

* **默认连接密码**：`1234`（VNC 与 SSH 均适用，可在 `docker-compose.yml` 中修改）

---

## 快速开始

### 1. 启动容器环境
在宿主机项目根目录下执行：
```bash
# 后台启动容器
docker compose up -d

# 查看实时日志
docker compose logs -f
```

### 2. 交互式使用 (VNC / 网页端)
* 访问 [http://localhost:6901](http://localhost:6901) 并输入密码 `1234` 即可进入 Debian 桌面环境。
* 桌面上挂载的 `workspace` 即为宿主机当前目录下的 `./workspace`，实现开发源码与容器配置解耦。

### 3. 配置 OpenCode 智能体环境
进入容器终端（可通过桌面终端或 `ssh default@localhost -p 2222` 登录），依次运行以下步骤以激活全部智能能力：

```bash
cd /headless/Desktop/workspace

# A. 连接远程 Ollama (以 100.102.149.107 为例) 并智能生成模型配置
bash setup_opencode_ollama.sh

# B. 安装 MCP 驱动（包括 mem0ai 记忆库、Playwright 浏览器等系统依赖）
python3 setup_mcp.py

# C. 安装 OpenCode 核心增强插件
python3 setup_plugin.py

# D. 导入 Agent 核心业务技能
python3 setup_skill.py
```

---

## 核心组件解析

### 1. init.sh 引导脚本
保持官方镜像的一致性，通过特权身份（`user: "0"`）在容器冷启动时按需运行：
* **用户与权限**：自动设置 `root` 密码，并检测/创建带 `sudo` 权限的常用用户 `default`。
* **SSH 模块**：自动安装并配置 `openssh-server`，修改 `sshd_config` 支持密码登录，生成主机密钥。
* **OpenCode 安装**：自动从官网拉取并启动 OpenCode 服务（端口 `4096`）。
* **新增系统依赖**：
  * `python3` & `python3-pip`：提供 Python 3 解释器与 pip3 工具包。
  * `python3-dev` & `build-essential`：提供 GCC 编译链及 Python 开发库，为 native/C++ 模块（如 `faiss` 检索库）编译提供支撑。
  * `jq`：轻量级命令行 JSON 处理工具。

### 2. workspace 工作区脚本

#### 📝 [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/workspace/setup_mcp.py)
配置 OpenCode 的 Model Context Protocol。
* **依赖包名修正**：由于官方 PyPI 包名调整，脚本中已将 `mem0` 依赖更新为 **`mem0ai`**。
* **Playwright 无头浏览器**：在 headless 容器中，Playwright 运行会缺失 Linux 图形底层组件。脚本使用 `playwright install --with-deps` 参数，能自动补充安装完备的系统级核心依赖包（如 `libgbm`、`libnss3`、`libasound`）。
* **自检逻辑**：写入 `mcp.config.json` 后，会自动校验配置文件结构的完整性。

#### 📝 [setup_opencode_ollama.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/workspace/setup_opencode_ollama.sh)
此脚本用于将 OpenCode 与远程 **Ollama** 大模型服务对接，并自动生成 `opencode.json` 配置。

- **连接信息**：`OLLAMA_HOST="100.102.149.107"`、`OLLAMA_PORT="11434"`（已写死在脚本顶部），对应远程 Ollama 实例。
- **模型过滤**：脚本现在仅会导入白名单中的两款模型：
  - `qwen3-coder:30b`
  - `mixtral:8x7b`
  通过 `whitelist` 变量实现，未在列表中的模型会被忽略。
- **默认模型**：在 `config['model']` 中自动选择 `qwen3-coder`（若存在）否则 `mixtral` 作为默认模型。
- **关键步骤**：
  1. 检测 `curl`、`jq`、`python3` 可用。
  2. 调用 Ollama `/api/tags` 获取模型列表并过滤白名单。
  3. 使用 Python 生成 OpenCode Provider 配置（`ollama-remote`），写入 `~/.config/opencode/opencode.json`。
  4. 验证配置文件是否生成。

> 此设计保证在多模型环境下，仅保留用户关心的模型，避免 `list` 占位符或无关模型污染配置。

对接外部 Ollama 算力中心（默认配置：`100.102.149.107:11434`）。
* **自动映射**：通过远程接口读取算力节点上已存在的所有模型。
* **智能判定**：使用 Python 精准识别如推理（Reasoning）和工具链调用（Tool Call）等高阶特性，并自动适配上下文长度限制。
* **热写入**：自动在本地写入或增量更新 `~/.config/opencode/opencode.json`，并一键热重启 OpenCode。

#### 📝 [setup_plugin.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/workspace/setup_plugin.py)
批量执行 OpenCode 插件安装。脚本会写入 `plugins.json`，并在写入前过滤掉非字符串或空值，防止出现意外的 "list" 占位符；自检阶段若检测到异常结构（如出现 "list"），会自动修复并重新写回合法插件列表。当前默认插件清单包括 `oh-my-opencode-slim`、`superpowers`、`opencode-pty`、`opencode-supermemory` 等 11 个模块，赋予 OpenCode 终端控制、沙盒运行和内存管理等能力。

#### 📝 [setup_skill.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/workspace/setup_skill.py)
批量导入 `bestof`、`comparisons`、`studying` 等 10 项 Agent 业务技能包，支撑知识库体系的构建与问答。

#### 📝 [restart_opencode.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/workspace/restart_opencode.sh)
快速热重启 OpenCode 服务工具。通过优雅结束进程（`pkill -f`）再到强制杀死（`pkill -9`），最后以守护进程方式重新拉起 Web 服务，并将日志流向 `/dockerstartup/custom/opencode_web.log`。

---

## 常用命令备忘

```bash
# 宿主机上：重启整个开发环境容器
docker compose restart

# 宿主机上：完全重建容器并清空暂存状态
docker compose down -v && docker compose up -d

# 容器内部：查看 OpenCode 启动与访问日志
tail -f /dockerstartup/custom/opencode_web.log

# 容器内部：附着进入 OpenCode 的后台进程终端
tmux attach -t opencode
```

---

## 问题排查

| 现象 | 可能原因 | 解决方案 |
| :--- | :--- | :--- |
| **容器一直循环重启** | `init.sh` 中的组件执行失败。 | 运行 `docker compose logs` 查阅启动流的 stdout/stderr 日志。 |
| **`setup_mcp.py` 报错找不到 pip3** | `init.sh` 执行时系统软件包更新尚未生效。 | 请确保 `init.sh` 中的 `setup_packages` 已成功跑完，或在容器中手动 `sudo apt-get update && sudo apt-get install -y python3-pip`。 |
| **Playwright 报错无法启动 Chromium** | 操作系统底层缺失 X11/GL 等共享库依赖。 | 脚本中已更新 `--with-deps`。请重新运行 `python3 setup_mcp.py` 以触发系统级依赖补全。 |
