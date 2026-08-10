# 需求文档 (Requirements & Checklist)

本文档跟踪项目功能的开发状态、需求核对以及未来的优化点。

## 1. 历史需求核对 (本次会话变更)

| 需求描述 | 状态 | 涉及组件/文件 | 备注 |
| :--- | :--- | :--- | :--- |
| **修复杂志/开发环境 Node 版本** | `已完成` | [container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) | 将 Node.js 版本从旧版升级到 Node 22 LTS，解决了 `better-sqlite3` 构建崩溃的问题。 |
| **修复 SQLite 远程 MCP 无法启动** | `已完成` | [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) | 升级 Node 22 解决编译问题，并将其调整为 `local` (stdio) 传输模式，彻底解决了 SSE 传输协议多连线单例冲突，顺利绿灯连线。 |
| **agent-browser 浏览器自动化集成** | `已完成` | [setup_agent_browser.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_agent_browser.py), [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py), [setup_skill.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_skill.py) | 新增 agent-browser 安装脚本，自动注册 agent-browser MCP 服务器，并将 agent-browser 作为 OpenCode skill 展示。 |
| **移除 Puppeteer 默认 MCP 服务** | `已完成` | [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) | 将 Puppeteer 从默认 MCP 配置中移除，改为使用 agent-browser 作为首选浏览器自动化引擎。 |
| **追加 `base_config` 基础开发配置** | `已完成` | [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) | 在 Python 代码中添加了全局 `base_config` 字典定义，用于插件及扩展模块开发时的配置查阅。 |
| **优化插件安装率与UI长名字问题** | `已完成` | [setup_plugin.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_plugin.py) | 采用 `bun install` 批量加载到项目依赖中，并在 `plugins.json` 写入时过滤掉长 URL，实现 100% 安装成功率与清爽的 WebUI 显示。 |
| **支持本地 `.deb` 安装 OpenCode** | `已完成` | [container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) | 修改 `setup_opencode` 函数优先通过 `apt-get` / `dpkg` 安装本地 `config/opencode-desktop-linux-arm64.deb` 软件包，并自动配置软链接。 |
| **精准控制 OpenCode CLI 版本为 v1.17.20** | `已完成` | [container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) | 锁定 `OPENCODE_TARGET_VERSION="1.17.20"`，精准控制 CLI 版本为 1.17.20，避免自动升级导致版本漂移。 |
| **规范 Agent 配置与忽略规则** | `已完成` | [.gitignore](file:///Users/esinternational/github/debian-xfce-vnc-dev/.gitignore), [docs/agent.md](file:///Users/esinternational/github/debian-xfce-vnc-dev/docs/agent.md) | 将 `.agents/` 加入 `.gitignore`，将 `agent.md` 规范平移至 `docs/agent.md` 并更新路径引用。 |
| **统一 Workspace 相对路径挂载** | `已完成` | [docker-compose.yml](file:///Users/esinternational/github/debian-xfce-vnc-dev/docker-compose.yml) | 将桌面 `workspace` 挂载路径从外部绝对路径统一调整为项目相对路径 `./workspace:/headless/Desktop/workspace`。 |
| **支持自定义 OpenCode WebUI Head Title** | `已完成` | [deploy.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/deploy.sh), [opencode_utils.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/opencode_utils.py), [container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) | 在 deploy 面板中新增 `OPENCODE_WEBUI_TITLE` 参数，支持动态对 OpenCode WebUI 的 HTML head `<title>` 进行修补，定制网页标签页标题。 |

---

## 2. 衍生出的优化需求与下一步计划 (待办)
- [ ] **优化 Docker 基础镜像构建**：在 Dockerfile 中直接安装 Node.js 22，以省去每次容器冷启动时 `container-init.sh` 在线更新的等待时间。
- [ ] **自动化证书/安全策略配置**：在后续若开启生产模式（`prod`），需要为 OpenCode 容器集成证书及密码控制。
