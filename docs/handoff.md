# 上下文交接文档 (Handoff Context)

本文档精简记录了当前会话的最新进展、环境状态与后续工作的交接说明。

## 1. 进展与当前状态

### 1.1 开发模式
- **当前模式**：`dev`（开发模式）。目前基于本地运行与调试。

### 1.2 已完成工作
1. **Node.js 22 升级**：[container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) 现包含自动将 Node 升级到 v22 的机制，解决 node-gyp 与 undici 冲突。
2. **SQLite MCP (local) 自动修复**：SQLite 顺利在容器内以 Stdio 管道由 OpenCode 自动拉起并运行，完美解决了 `Already connected to a transport` 的多连线单例冲突。
3. **Puppeteer MCP (local) 配置补全**：在 [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) 中，已成功注入 `ALLOW_DANGEROUS: "true"` 和 `--no-sandbox` 参数，解决了进程挂起问题。
4. **追加 `base_config` 变量**：在 [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) 中，声明了包含插件默认配置信息的 `base_config` 字典，避免将其硬编码入 `opencode.jsonc` 产生 Schema 校验错误。
5. **支持本地 `.deb` 包极速安装 OpenCode**：在 [container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) 中加入了优先检测并使用 `apt-get` 安装本地 `config/opencode-desktop-linux-arm64.deb` 软件包的逻辑，实现离线/低延迟极速安装。
6. **统一 Workspace 相对挂载路径**：将 [docker-compose.yml](file:///Users/esinternational/github/debian-xfce-vnc-dev/docker-compose.yml) 与 [docker-compose-dev.yml](file:///Users/esinternational/github/debian-xfce-vnc-dev/docker-compose-dev.yml) 中的桌面工作区挂载由外部绝对路径统一优化为本地相对路径 `./workspace:/headless/Desktop/workspace`。

---

## 2. 后续待办事项 (Todo List)
1. **模式转换决策**：等待男神欧巴下达是否转换成 `prod`（生产模式）的命令。
2. **远程推送**：等待男神欧巴下达将代码 push 到 GitHub 的指令（当前仅作本地 commit 记录）。
3. **测试扩展插件的配置文件挂载**：待后续插件（如 `opencode-agent-skills`）正式装载后，需要联调测试它们是否能顺利读取相应的 `base_config` 预设。
