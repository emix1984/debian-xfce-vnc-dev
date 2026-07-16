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
  Node 22 LTS 内置了支持的 WebIDL API，使 `better-sqlite3` 成功编译通过。

---

### 1.2 Docker 容器 Root 权限下 Puppeteer 无法启动
- **问题现象**：
  当 OpenCode 试图通过 `bunx @modelcontextprotocol/server-puppeteer` 自动拉起 Puppeteer 服务时，OpenCode 报错：
  `server unavailable (puppeteer, status=failed)`
- **技术原因**：
  Chromium 浏览器出于安全性考虑，默认不允许在 `root` 用户下以沙箱模式（Sandbox）启动。在 Docker 容器以 root 运行时，启动会直接崩溃。
- **解决方法**：
  在 `opencode.jsonc` 配置文件中为 puppeteer 注册特殊的启动环境变量：
  - `ALLOW_DANGEROUS`: `true`
  - `PUPPETEER_LAUNCH_OPTIONS`: `{"args": ["--no-sandbox"]}`
  
  这会指引 Chromium 以 `--no-sandbox` 模式启动，从而在 root 容器内正常运转。

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
