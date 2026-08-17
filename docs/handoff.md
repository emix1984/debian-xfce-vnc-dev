# 上下文交接文档 (Handoff Context)

本文档精简记录了当前会话的最新进展、环境状态与后续工作的交接说明。

## 1. 进展与当前状态

### 1.1 开发模式
- **当前模式**：`dev`（开发模式）。目前基于本地运行与调试。

### 1.2 已完成工作
1. **Node.js 22 升级**：[container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) 现包含自动将 Node 升级到 v22 的机制，解决 node-gyp 与 undici 冲突。
2. **SQLite MCP (local) 自动修复**：SQLite 顺利在容器内以 Stdio 管道由 OpenCode 自动拉起并运行，完美解决了 `Already connected to a transport` 的多连线单例冲突。
3. **agent-browser 浏览器自动化集成**：新增 [setup_agent_browser.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_agent_browser.py)，自动安装 `agent-browser` CLI，并在 [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) 中注册 `agent-browser` MCP 服务，支持 OpenCode 直接调用浏览器自动化能力。`config/container-init.sh` 现会自动执行 `setup_agent_browser.py`、`setup_mcp.py`、`setup_plugin.py` 与 `setup_skill.py`，将初始化流程模块化。
4. **Puppeteer MCP 已移除**：`setup_mcp.py` 按需加载 MCP 服务的机制已升级，不再默认启动 `puppeteer`，避免无谓的浏览器进程与容器资源开销。

补充说明：
- `setup_webui_title.sh` 为 Python 脚本，容器启动时由 `python3` 调用以修补 WebUI `<title>`（避免用 `bash` 直接执行造成解析错误）。
- OpenCode WebUI 的启动与重启使用 `tmux` 会话 (`opencode_web`)，并在 `restart_opencode.sh` 中也使用 `tmux` 来保证后台运行可靠性与日志聚合。
5. **追加 `base_config` 变量**：在 [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) 中，声明了包含插件默认配置信息的 `base_config` 字典，避免将其硬编码入 `opencode.jsonc` 产生 Schema 校验错误。
6. **支持本地 `.deb` 包极速安装 OpenCode**：在 [container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) 中加入了优先检测并使用 `apt-get` 安装本地 `config/opencode-desktop-linux-arm64.deb` 软件包的逻辑，实现离线/低延迟极速安装。
6. **统一 Workspace 相对挂载路径**：将 [docker-compose.yml](file:///Users/esinternational/github/debian-xfce-vnc-dev/docker-compose.yml) 中的桌面工作区挂载由外部绝对路径统一优化为本地相对路径 `./workspace:/headless/Desktop/workspace`。
7. **支持自定义 OpenCode WebUI Head Title**：在 [deploy.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/deploy.sh) 中新增了 `OPENCODE_WEBUI_TITLE` 配置，在容器初始化与热重启时自动对 `opencode` 可执行文件的 HTML head `<title>` 进行等长修补，支持定制化网页标签页标题。

---

## 2. 后续待办事项 (Todo List)
1. **模式转换决策**：等待男神欧巴下达是否转换成 `prod`（生产模式）的命令。
2. **远程推送**：代码已推送到 GitHub（origin/main）。
3. **测试扩展插件的配置文件挂载**：待后续插件（如 `opencode-agent-skills`）正式装载后，需要联调测试它们是否能顺利读取相应的 `base_config` 预设。
4. **更新流程说明**：`deploy.sh` 已实现非破坏性的交互式更新菜单（在执行任何更新前会 `git fetch` 并显示远端/本地差异摘要；支持 `fast-forward` / `merge` / `rebase` / `stash`+pull 多种选择），并明确保护容器内的 `/headless/Desktop/workspace` 文件夹不被删除或清空。
