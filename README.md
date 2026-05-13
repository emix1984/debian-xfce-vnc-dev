# Debian Xfce VNC 容器

基于 [consol/debian-xfce-vnc](https://github.com/ConSol/docker-headless-vnc-container) 官方镜像，通过 `docker-compose.yml` + `init.sh` 实现启动时自定义配置。

**核心思路**：不修改 Dockerfile，保持镜像一致性。所有自定义逻辑写在 `init.sh` 中，任何环境（本地、服务器、CI）都用同一个镜像。

---

## 目录结构

```
debian/
├── docker-compose.yml    # 容器编排 — 挂载 init.sh、配置端口/环境变量
├── init.sh               # 启动时自动执行的初始化脚本
└── README.md             # 本文件
```

---

## 快速开始

```bash
# 启动容器（前台看日志）
docker compose up

# 或后台启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止并清理
docker compose down
```

---

## 访问方式

| 服务 | 地址 | 说明 |
|------|------|------|
| VNC 客户端 | `vnc://localhost:5901` | 用 VNC Viewer 连接 |
| noVNC 网页 | `http://localhost:6901` | 浏览器直接访问 |
| SSH | `ssh default@localhost -p 2222` | 命令行远程登录 |

默认密码：`1234`

---

## 工作原理

### 启动流程

```
docker compose up
    │
    ├─ 1. Docker 挂载 ./init.sh → 容器内 /dockerstartup/custom/init.sh
    │
    ├─ 2. 执行 entrypoint（覆盖镜像默认入口）
    │      │
    │      ├─ mkdir -p /dockerstartup/custom   ← 确保目录存在
    │      │
    │      ├─ /dockerstartup/custom/init.sh    ← 执行初始化脚本
    │      │      │
    │      │      ├─ 设置 root 密码
    │      │      ├─ 创建 default 用户 & 设置密码 & 加入 sudo
    │      │      ├─ 安装 openssh-server（如未安装）
    │      │      ├─ 配置 SSH（允许密码登录、允许 root）
    │      │      └─ 启动 SSH 服务
    │      │
    │      └─ exec /dockerstartup/vnc_startup.sh  ← 启动 VNC
    │
    └─ 3. 容器正常运行：VNC(5901) + noVNC(6901) + SSH(22)
```

### 为什么不使用 Dockerfile？

| 方式 | 问题 |
|------|------|
| Dockerfile 定制 | 每处环境都需要重新 build，镜像版本不可控 |
| init.sh 方式 | 同一份镜像到处跑，自定义逻辑在 `init.sh` 中按需修改 |

你只需要维护 `docker-compose.yml` + `init.sh`，不需要管镜像构建。

---

## init.sh 详解

### 做了什么

| 模块 | 功能 | 幂等 |
|------|------|------|
| `setup_users` | 设置 root 密码，创建 `default` 用户并加入 sudo | ✅ 检测用户存在则跳过 |
| `setup_ssh` | 安装 openssh-server，生成密钥，配置 SSHD | ✅ 检测包/密钥存在则跳过 |

幂等 = 容器重启时不会重复安装或报错，每次执行结果一致。

### 怎么改

`init.sh` 可自由扩展，例如：

```bash
# 在 setup_users 中加新用户
useradd -m -s /bin/bash admin
echo "admin:admin" | chpasswd

# 安装软件
apt-get install -y vim curl

# 写配置文件
echo "custom config" > /etc/myapp.conf
```

### 日志

- **Docker 终端**：`docker compose logs` 即可看到 init.sh 的全部输出
- **容器内日志文件**：`/dockerstartup/custom/init.log`
  ```bash
  docker exec debian-xfce-vnc cat /dockerstartup/custom/init.log
  ```
- 重启时日志追加（不覆盖）

---

## 环境变量

在 `docker-compose.yml` 的 `environment:` 中修改：

| 变量 | 当前值 | 说明 |
|------|--------|------|
| `VNC_PW` | `1234` | VNC 连接密码 |
| `VNC_RESOLUTION` | `1280x720` | 桌面分辨率 |
| `TZ` | `Asia/Seoul` | 时区 |

示例：
```yaml
environment:
  - VNC_PW=mysecret
  - VNC_RESOLUTION=1920x1080
  - TZ=Asia/Shanghai
```

---

## docker-compose.yml 关键配置解析

```yaml
user: "0"
```
以 root 身份运行。原因：init.sh 需要执行 `useradd`、`chpasswd`、`apt-get` 等特权操作。

```yaml
entrypoint:
  - /bin/bash
  - -c
  - |
    mkdir -p /dockerstartup/custom
    /dockerstartup/custom/init.sh && exec /dockerstartup/vnc_startup.sh "$$@"
  - --
```
覆盖镜像默认入口。先执行 init.sh，成功后才启动 VNC；init.sh 失败则容器退出，便于排查。

```yaml
volumes:
  - ./init.sh:/dockerstartup/custom/init.sh:ro
```
将宿主机的 `init.sh` 挂载到容器内，`:ro` 表示只读（容器内不能修改）。这样修改宿主机文件即可生效。

---

## 端口映射

| 容器端口 | 宿主机端口 | 用途 |
|----------|------------|------|
| 5901 | 5901 | VNC 协议（桌面连接） |
| 6901 | 6901 | noVNC 网页客户端 |
| 22 | 2222 | SSH |

如需修改宿主机端口，编辑 `docker-compose.yml` 中 `ports:` 部分即可。

---

## 常用命令

```bash
# 启动
docker compose up -d

# 查看实时日志
docker compose logs -f

# 进入容器
docker compose exec debian-xfce-vnc bash

# 重启
docker compose restart

# 停止并删除容器
docker compose down

# 完全重建（清除所有状态）
docker compose down -v && docker compose up -d
```

---

## 问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 容器不断重启 | init.sh 执行失败 | `docker compose logs` 查看错误信息 |
| init.sh 变更不生效 | 需要重建容器 | `docker compose down && docker compose up -d` |
| noVNC 页面打不开 | 端口被占用 | 修改 ports 中的 6901 映射端口 |
| SSH 连不上 | SSH 服务未启动 | 检查 init.sh 中 SSH 安装是否正常 |

---

## 与官方镜像的关系

| 项目 | 官方默认 | 本配置 |
|------|----------|--------|
| 运行时用户 | `default` (UID 1000) | `root`（通过 `user: "0"`） |
| 入口脚本 | `vnc_startup.sh` | 先跑 `init.sh` → 再跑 `vnc_startup.sh` |
| SSH | 无 | init.sh 自动安装并配置 |
| 自定义用户 | 无 | `default` 用户带 sudo 权限 |
| root 密码 | 无 | 初始化为 `1234` |

---

## 许可证

Apache-2.0 License
