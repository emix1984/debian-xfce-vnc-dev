# 项目技能文档 (Project Skills & Troubleshooting)

本文档记录了项目开发过程中新引入的技术栈、解决的复杂技术难点、踩坑记录及特定命令。

## 1. 踩坑记录与解决方案

### 1.1 `better-sqlite3` 编译与 Node-gyp WebIDL 错误
- **问题现象**：
  在 Node.js `v20.20.2` 下，使用 `bunx` / `npm` 安装并编译 `better-sqlite3` 依赖时，`node-gyp` 抛出以下错误：
  ```
  gyp ERR! stack TypeError: webidl.util.markAsUncloneable is not a function
  gyp ERR! stack at new CacheStorage (/tmp/bunx-0-node-gyp@latest/node_modules/undici/lib/web/cache/cachestorage.js:20:17)
  ```
- **技术原因**：
  新版的 `undici` 包依赖了 Node.js 较新版本中引入的内部 `worker_threads.markAsUncloneable` API。因为基础镜像里的 Node.js `v20.20.2` 比较老，未提供此 API，导致构建脚本在试图下载或编译二进制原生插件时崩溃。
- **解决方法**：
  在初始化容器时，通过 NodeSource 源将 Node.js 强制更新到 Node 22 LTS：
  ```bash
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
  ```
  Node 22 LTS 内置了支持 of WebIDL API，使 `better-sqlite3` 成功编译通过。

---

### 1.3 `@pepk/mcp-memory-sqlite` 的 SSE 传输协议多连接冲突 (Already connected to a transport)
- **问题现象**：
  在将 SQLite 配置为 `remote`（HTTP/SSE）模式后，OpenCode 对其的多次查询或多连接会导致服务器抛出：
  `Error: Already connected to a transport. Call close() before connecting to a new transport, or use a separate Protocol instance per connection.`
  从而导致 sqlite MCP 服务连线断开，在 `opencode mcp list` 中显示为红色的 `✗ failed`。
- **技术原因**：
  该包的 SSE HTTP 服务器使用的是单例（Singleton）模式构建 `McpServer` 实例。当客户端（OpenCode WebUI 等）建立第二个 HTTP 连线或刷新連線時，伺服器會嘗試將已連接的 Server 單例重新連接到新傳輸通道，引發 MCP SDK 底層保護機制報措。
- **解决方法**：
  将其修改为 `local`（Stdio）模式。Stdio 管道是 1:1 的直接進程通信管道，OpenCode 獨立維護生命週期，不會引發併發連線衝突。

---

### 1.2 Docker 容器 Root 权限下 Puppeteer 无法启动
- **问题现象**：
  当 OpenCode 试图通过 `bunx @modelcontextprotocol/server-puppeteer` 自动拉起 Puppeteer 服务时，OpenCode 报错：
  `server unavailable (puppeteer, status=failed)`
- **技术原因**：
  Chromium 浏览器出于安全性考虑，默认不允许在 `root` 用户下以沙箱模式（Sandbox）启动。在 Docker 容器以 root 运行时，启动会直接崩溃。
- **解决方法**：
  In `opencode.jsonc` 配置文件中为 puppeteer 注册特殊的启动环境变量：
  - `ALLOW_DANGEROUS`: `true`
  - `PUPPETEER_LAUNCH_OPTIONS`: `{"args": ["--no-sandbox"]}`
  
  这会指引 Chromium 以 `--no-sandbox` 模式启动，从而在 root 容器内正常运转。

---

### 1.4 OpenCode 插件安装失败及 WebUI 面板显示名称过长
- **问题现象**：
  1. 通过 `opencode plugin` 逐个串行安装 Git 插件时，由于 OpenCode 内部 npm 包管理器对 Git 依赖处理不稳定，非常容易发生构建超时或崩溃（报错 `git dep preparation failed`）。
  2. 安装成功后，WebUI 插件面板中显示的插件名称很长，甚至直接带着完整的 GitHub 链接（例如 `oh-my-opencode-slim@git+https://...`）。
- **技术原因**：
  1. npm 直接拉取 Git 代码进行 prepare 的过程极其缓慢且不可靠。
  2. 脚本在 `/headless/.opencode/plugins.json` 中写入了完整的安装标识符（URL），导致 WebUI 加载时把 URL 识别为插件的名字展现出来。
- **解决方法**：
  1. 在 `setup_plugin.py` 中，改为将所有依赖以 `{包名: Git地址}` 形式写入 `/headless/.opencode/package.json`，并执行 `bun install` 批量拉取并链接到 `node_modules`。这不仅避免了超时构建错误，且耗时降为数秒级。
  2. 修改 `write_plugin_list` 逻辑，在写入 `plugins.json` 时，通过 `.split('@')[0]` 过滤只保留简短、纯净的包名。重置并重启 WebUI 服务后，显示界面就会恢复整洁美观。

---

## 2. 常用开发与维护命令

### 2.1 重新初始化并启动 MCP 配置
在容器控制台或通过 `docker exec` 主动执行以下命令来重新生成 MCP 配置并重启 WebUI：
```bash
docker exec debian-xfce-vnc bash -c "cd /headless/Desktop/config && python3 setup_mcp.py"
```

### 2.2 查看 OpenCode 服务运行日志
```bash
docker exec debian-xfce-vnc tail -n 100 /headless/.local/share/opencode/log/opencode.log
```
