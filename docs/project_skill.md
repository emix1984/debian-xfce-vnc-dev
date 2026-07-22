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

### 1.5 OpenCode DEB 桌面包与 CLI 可执行文件的职责分离及 4096 端口无法访问排障
- **问题现象**：
  在配置了本地 `opencode-desktop-linux-arm64.deb` 安装后，重建容器时启动后台 `opencode web --hostname 0.0.0.0 --port 4096` 失败，4096 端口无法响应，`opencode_web.log` 报错：
  `FATAL:electron/shell/app/electron_main_delegate.cc:219] Running as root without --no-sandbox is not supported.`
- **技术原因**：
  1. `opencode-desktop-linux-arm64.deb` 安装的是 OpenCode 的 Electron 桌面 GUI 程序 (`/opt/OpenCode/ai.opencode.desktop`)，用于 Linux 桌面环境。
  2. 之前脚本误将 `/usr/bin/opencode` 软链接到了桌面 GUI 程序，导致后台运行 `opencode web` 时错误拉起 Electron GUI，触发 root 免沙箱崩溃，未拉起 CLI HTTP 服务器。
- **解决方法**：
  1. 保持 `.deb` 桌面程序的正常安装，提供 VNC 桌面 GUI 支持。
  2. 明确将 `/usr/bin/opencode` 软链接指向 CLI 二进制文件 `${OPENCODE_BIN}` (`/headless/.opencode/bin/opencode`)。
  3. 在 `container-init.sh` 和 `restart_opencode.sh` 中显式通过 `${OPENCODE_BIN} web` 启动 4096 端口 HTTP WebUI 服务。

---

### 1.6 Bun 独立可执行二进制文件的等长字节修改机制
- **问题现象**：
  OpenCode 官方 WebUI 页面在 `headless/.opencode/bin/opencode` 二进制文件中硬编码了 `<title>OpenCode</title>`。如果直接用普通的字符串替换来修改此标题，当修改后的字符串长度与原字符串不一致时，启动 binary 会直接报错：
  `error: Script not found "web"`
- **技术原因**：
  `opencode` 是由 Bun 构建的独立可执行文件（Bun Standalone Executable），它的二进制文件尾部附加了 JS/ZIP 资源包，且在特定字节偏移位置有固定的大小和索引。若修改文件字节长度，会导致偏移量失效，Bun 退化为普通 CLI 并寻找本地的 `web` 脚本。
- **解决方法**：
  采用**精确字节等长修补法**。在 [config/opencode_utils.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/opencode_utils.py) 中，定位到 `<title>...</title>` 所在的 350 字节窗口，将新的 `<title>新标题</title>` 写入该窗口，若长度不足，用空格补齐以填充剩余字节，若长度超出，则截断，确保文件总大小 **100% 字节保持原样不变**。写入前使用 `pkill -f "opencode web"` 確保釋放二進制文件句柄（規避 Linux `Text file busy` 錯誤），从而完美實現中文自定義網頁標題。

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
