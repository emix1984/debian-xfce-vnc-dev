# 需求文档 (Requirements & Checklist)

本文档跟踪项目功能的开发状态、需求核对以及未来的优化点。

## 1. 历史需求核对 (本次会话变更)

| 需求描述 | 状态 | 涉及组件/文件 | 备注 |
| :--- | :--- | :--- | :--- |
| **修复杂志/开发环境 Node 版本** | `已完成` | [container-init.sh](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/container-init.sh) | 将 Node.js 版本从旧版升级到 Node 22 LTS，解决了 `better-sqlite3` 构建崩溃的问题。 |
| **修复 SQLite 远程 MCP 无法启动** | `已完成` | [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) | 升级 Node 22 解决编译问题，并将其调整为 `local` (stdio) 传输模式，彻底解决了 SSE 传输协议多连线单例冲突，顺利绿灯连线。 |
| **配置 Puppeteer 默认容器启动参数** | `联调成功` | [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) | 添加了 `ALLOW_DANGEROUS` 和 `--no-sandbox` 环境变量，规避了 root 用户下沙箱启动失败的问题。 |
| **追加 `base_config` 基础开发配置** | `已完成` | [setup_mcp.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_mcp.py) | 在 Python 代码中添加了全局 `base_config` 字典定义，用于插件及扩展模块开发时的配置查阅。 |
| **优化插件安装率与UI长名字问题** | `已完成` | [setup_plugin.py](file:///Users/esinternational/github/debian-xfce-vnc-dev/config/setup_plugin.py) | 采用 `bun install` 批量加载到项目依赖中，并在 `plugins.json` 写入时过滤掉长 URL，实现 100% 安装成功率与清爽的 WebUI 显示。 |

---

## 2. 衍生出的优化需求与下一步计划 (待办)
- [ ] **优化 Docker 基础镜像构建**：在 Dockerfile 中直接安装 Node.js 22，以省去每次容器冷启动时 `container-init.sh` 在线更新的等待时间。
- [ ] **自动化证书/安全策略配置**：在后续若开启生产模式（`prod`），需要为 OpenCode 容器集成证书及密码控制。
