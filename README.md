# Debian Xfce VNC 智能开发与 Agent 工作站

基于 [consol/debian-xfce-vnc](https://github.com/ConSol/docker-headless-vnc-container) 官方镜像，通过 `docker-compose.yml` + `container-init.sh` 构建的免编译、即插即用型 AI Agent 开发与测试沙盒环境。

本工作站已深度集成 **OpenCode**（一款先进的本地开发与智能体执行框架），并配备了完善的 MCP（Model Context Protocol）能力配置脚本、远程 LLM（Ollama）智能对接方案，以及自动化插件与技能分发体系。

---

## 目录结构

项目采用了**配置脚本与业务代码物理隔离**的最佳实践：

```text
debian-xfce-vnc-dev/
├── docker-compose.yml          # 容器编排 — 端口映射、目录挂载及系统变量
├── docker-compose-dev.yml      # 开发专用编排 — 剥离了脚本依赖，硬编码变量，取消了自动重启，方便本地调试
├── deploy.sh                   # 工作站交互式控制面板 — 自动化管理容器与配置
├── .deploy_config              # (自动生成) 私有配置文件，隔离环境变量，防覆盖
├── .gitignore                  # 高度优化的 Git 忽略规则，防止业务代码污染基础架构
├── config/                     # 专属环境配置与自动化脚本目录
│   ├── container-init.sh       # 容器初次启动引导脚本
│   ├── restart_opencode.sh     # OpenCode Web 服务一键热重启工具
│   ├── setup_mcp.py            # MCP 依赖及配置安装脚本（含 mem0ai、Playwright 等）
│   ├── setup_opencode_ollama.sh# 远程 Ollama 大模型连接与自动导入脚本
│   ├── setup_plugin.py         # OpenCode 插件管理工具
│   └── setup_skill.py          # OpenCode 技能包导入工具
└── workspace/                  # 纯净工作空间（挂载至容器桌面 `/headless/Desktop/workspace`）
    └── .gitkeep                # 仅作为结构占位，您的所有业务代码在此存放并被 Git 忽略
```

---

## 交互式控制面板 (deploy.sh)

在宿主机项目根目录下执行 `./deploy.sh` 即可启动图形化终端控制面板，提供以下一键式服务：

- **启停/重置环境**：优雅地启动、停止或彻底清空容器与数据卷。
- **自定义参数设置**：修改 VNC 端口、分辨率（默认 1280x1024）、连接密码、大模型节点 IP。
- **一键配置 Agent 工作流**：按序自动执行 Ollama 发现、安装 MCP、载入插件与技能包。
- **工作区备份与清理**：在执行破坏性测试后，可一键备份现有工作区（生成 `workspace_*.bak` 文件夹）并秒级重建纯净的全新工作区。
- **系统环境状态**：动态穿透容器，一键查看内部操作系统版本、Python 版本、OpenCode 版本及核心配置文件挂载路径。

---

## 访问与服务端口

容器启动后，将对外暴露以下通信与管理接口：

| 服务 | 宿主机映射地址 | 容器内部端口 | 说明 |
| :--- | :--- | :--- | :--- |
| **VNC 桌面** | `vnc://localhost:5901` | `5901` | 使用 VNC Viewer 等客户端直接访问系统桌面 |
| **noVNC 网页版** | `http://localhost:6901` | `6901` | 浏览器直接访问的桌面终端，适合无客户端环境 |
| **SSH 服务** | `ssh default@localhost -p 2222` | `22` | 宿主机终端命令行远程登录容器（默认密码 `1234`） |
| **OpenCode WebUI**| `http://localhost:4096` | `4096` | OpenCode 内置开发者 Web 交互与 Agent 控制界面 |

---

## 快速开始

### 1. 启动容器环境

**方式一：使用控制面板（推荐日常使用）**
执行控制面板：
```bash
./deploy.sh
```
在菜单中选择 `1) Start/Up Environment` 启动容器。

**方式二：以开发模式启动（推荐调试排错）**
直接使用开发专用配置启动，该模式剥离了外部变量依赖并关闭了自动重启，适合直接观察报错日志：
```bash
docker compose -f docker-compose-dev.yml up -d
```

### 2. 交互式使用 (VNC / 网页端)
* 访问 [http://localhost:6901](http://localhost:6901) 并输入密码即可进入 Debian 桌面环境。
* 桌面上挂载的 `workspace` 文件夹是一个纯净的开发沙盒；`config` 文件夹内包含了所有的系统安装与连接脚本。

### 3. 配置 OpenCode 智能体环境
在 `./deploy.sh` 面板菜单中选择 `5) Run Workspace Init Scripts`，然后选择 `5) [Run All] Sequential Setup` 以自动按序完成：
1. **Ollama 大模型对接**：自动扫描远程算力节点并导入模型（如 `qwen3-coder:30b` 及 `mixtral:8x7b`）。
2. **MCP 驱动安装**：利用 `--with-deps` 补全 `Playwright` 浏览器在 headless 环境下的底层依赖。
3. **插件安装**：载入如 `oh-my-opencode-slim` 等高级开发能力插件。
4. **技能包导入**：赋予 Agent 任务拆解、网页访问、代码对比等各项技能。

---

## 核心底层机制解析

### 1. container-init.sh 引导机制
* **网络降级保底容错**：安装 OpenCode 核心服务时，若遭遇 GitHub API 限流报错（`Failed to fetch version information`），脚本会自动触发 **1.17.9 指定版本降级安装机制**，确保容器能够 100% 成功完成初始化，杜绝因网络阻断而死锁。
* **用户与权限统一**：自动将 `root` 用户的 HOME 目录修正为 `/headless`，与 VNC 桌面环境对齐，避免因双 HOME 路径造成的权限混乱或项目列表撕裂。
* **隔离策略**：OpenCode 的全局配置文件统一约束在 `/headless/.config/opencode`，与用户私有源码区完全分离。

### 2. 自动化配置脚本群 (config 目录)

* **setup_opencode_ollama.sh**：
  从远程算力节点拉取模型列表并过滤白名单，自动转换为 OpenCode 的 Provider。
* **setup_mcp.py**：
  配置 `mcp.config.json`，解决 Linux `headless` 环境下原生系统级共享库（X11/GL 等）缺失的顽疾。
* **setup_plugin.py**：
  负责写入 `plugins.json`。脚本内含自检逻辑，防止因旧版本残留配置、异常数组占位符造成的后台 Node.js 进程在加载 Workspace 时死锁挂起。

---

## 问题排查

| 现象 | 可能原因 | 解决方案 |
| :--- | :--- | :--- |
| **打开 OpenCode 网页不加载大模型或设置点不动** | 由于第三方不兼容插件或无权限环境导致内部 `plugins.json` 在后台进程中死锁。 | 运行 `./deploy.sh` 并在菜单中选择 `11) Backup & Clean Workspace` 一键重建纯净工作区。 |
| **容器一直循环重启** | `container-init.sh` 中遇到致命环境阻断。 | 在菜单中选择 `4) View Container Logs` 查阅启动流的详细日志。 |
| **无法显示工作区项目列表** | 容器启动时强制切换了目录或环境错位。 | 本项目已移除全部有风险的预设 `cd` 逻辑，OpenCode 现在以根目录全局透视模式启动。 |
