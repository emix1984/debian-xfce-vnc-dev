#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

LOG_DIR="/dockerstartup/custom"
LOG_FILE="${LOG_DIR}/init.log"
mkdir -p "${LOG_DIR}"
touch "${LOG_FILE}"
chmod 644 "${LOG_FILE}"

# 重定向日志到文件并记录 tee 的 PID
exec > >(tee -a "${LOG_FILE}") 2>&1
TEEPID=$!
echo "${TEEPID}" > /tmp/.init_tee.pid

cleanup() {
  if [ -n "${TEEPID:-}" ] && ps -p "${TEEPID}" >/dev/null 2>&1; then
    kill "${TEEPID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# =====================================
# OpenCode 路径配置 - 在 consol/debian-xfce-vnc 容器中
# =====================================
# consol/debian-xfce-vnc 容器中 root 用户的 HOME 是 /headless
export ACTUAL_HOME="${ACTUAL_HOME:-/headless}"
export OPENCODE_HOME="${OPENCODE_HOME:-${ACTUAL_HOME}/.opencode}"
export OPENCODE_CONFIG_DIR="${OPENCODE_CONFIG_DIR:-${ACTUAL_HOME}/.config/opencode}"
export OPENCODE_PLUGINS_DIR="${OPENCODE_HOME}/plugins"
export OPENCODE_BIN="${OPENCODE_HOME}/bin/opencode"

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] container-init.sh START"
echo "========================================"
echo "[INFO] Container environment: ACTUAL_HOME=${ACTUAL_HOME}, OPENCODE_HOME=${OPENCODE_HOME}"

apt_install() {
  local pkgs=("$@")
  if [ "${#pkgs[@]}" -eq 0 ]; then
    return 0
  fi
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y --no-install-recommends -qq "${pkgs[@]}"
}

setup_users() {
  echo ""
  echo "--- [setup_users] ---"

  # 安全提示：生产环境请不要硬编码密码，使用环境变量或 secret 管理
  ROOT_PASS="${ROOT_PASS:-1234}"
  DEFAULT_PASS="${DEFAULT_PASS:-1234}"

  echo "root:${ROOT_PASS}" | chpasswd
  echo "[INFO] Root password set."

  if ! id default >/dev/null 2>&1; then
    useradd -m -s /bin/bash default
    echo "[INFO] User 'default' created."
  else
    echo "[INFO] User 'default' already exists."
  fi

  echo "default:${DEFAULT_PASS}" | chpasswd
  echo "[INFO] Default password set."

  if getent group sudo >/dev/null 2>&1; then
    usermod -aG sudo default || true
  elif getent group wheel >/dev/null 2>&1; then
    usermod -aG wheel default || true
  fi
  echo "[INFO] Default user added to sudo group if available."

  if id default >/dev/null 2>&1; then
    echo "[INFO] Default user check PASSED."
  else
    echo "[ERROR] Default user check FAILED."
    exit 1
  fi
}

setup_ssh() {
  echo ""
  echo "--- [setup_ssh] ---"

  if ! dpkg -s openssh-server >/dev/null 2>&1; then
    echo "[INFO] Installing openssh-server..."
    apt_install openssh-server
    echo "[INFO] openssh-server installed."
  else
    echo "[INFO] openssh-server already installed."
  fi

  mkdir -p /var/run/sshd

  # 生成缺失的主机密钥
  ssh-keygen -A || true

  SSHD_CONF="/etc/ssh/sshd_config"
  if [ -f "${SSHD_CONF}" ]; then
    sed -i '/^\s*PermitRootLogin\s\+/Id' "${SSHD_CONF}" || true
    sed -i '/^\s*PasswordAuthentication\s\+/Id' "${SSHD_CONF}" || true
    {
      echo "PermitRootLogin yes"
      echo "PasswordAuthentication yes"
    } >> "${SSHD_CONF}"
  else
    echo "[ERROR] ${SSHD_CONF} not found."
    exit 1
  fi

  if grep -q "^PermitRootLogin yes" "${SSHD_CONF}" && grep -q "^PasswordAuthentication yes" "${SSHD_CONF}"; then
    echo "[INFO] SSH config updated successfully."
  else
    echo "[ERROR] SSH config update FAILED."
    exit 1
  fi

  if ! pgrep -x sshd >/dev/null 2>&1; then
    /usr/sbin/sshd || { echo "[ERROR] Failed to start sshd"; exit 1; }
    echo "[INFO] SSH service started."
  else
    echo "[INFO] SSH service already running."
  fi
}

setup_packages() {
  echo ""
  echo "--- [setup_packages] ---"

  PACKAGES=(
    git
    curl
    wget
    nano
    unzip
    tmux
    geany
    python3
    python3-pip
    python3-dev
    build-essential
    jq
  )

  MISSING=()
  for pkg in "${PACKAGES[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      MISSING+=("$pkg")
    fi
  done

  if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[INFO] Installing missing packages: ${MISSING[*]}"
    apt_install "${MISSING[@]}"
  else
    echo "[INFO] All packages already installed."
  fi
}

setup_node() {
  echo ""
  echo "--- [setup_node] ---"

  local current_ver=""
  if command -v node >/dev/null 2>&1; then
    current_ver=$(node -v | cut -d'v' -f2)
    echo "[INFO] Current Node version: v${current_ver}"
  fi

  # If node is not present, or its major version is less than 22, install/upgrade to v22
  if [ -z "${current_ver}" ] || [ "$(echo "${current_ver}" | cut -d'.' -f1)" -lt 22 ]; then
    echo "[INFO] Installing/Upgrading Node.js v22 via NodeSource..."
    apt_install curl ca-certificates gnupg2 apt-transport-https
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt_install nodejs
    if command -v node >/dev/null 2>&1; then
      echo "[INFO] Node installed/upgraded to: $(node --version 2>&1)"
    else
      echo "[ERROR] Node installation/upgrade failed"
      exit 1
    fi
  else
    echo "[INFO] Node.js version $(node -v) is already v22+, skipping installation."
  fi

  # Ensure npm exists and install bun (bunx) if missing
  if command -v bunx >/dev/null 2>&1; then
    echo "[INFO] bunx already present: $(bunx --version 2>&1 || true)"
  else
    if command -v npm >/dev/null 2>&1; then
      echo "[INFO] Installing bun via npm..."
      npm install -g bun || echo "[WARN] npm install -g bun failed"
      if command -v bunx >/dev/null 2>&1; then
        echo "[INFO] bunx installed: $(bunx --version 2>&1 || true)"
      else
        echo "[WARN] bunx not found after npm install"
      fi
    else
      echo "[WARN] npm not available; cannot install bun automatically"
    fi
  fi
}

setup_opencode() {
  echo ""
  echo "--- [setup_opencode] ---"

  # -------------------------------------------------------
  # 修正 /etc/passwd 中 root 的 HOME 目录
  # consol/debian-xfce-vnc 容器以 user:0 运行，但镜像默认
  # /etc/passwd 中 root 的 HOME 是 /root，而环境变量 HOME=/headless。
  # OpenCode 会同时参考 $HOME 和 /etc/passwd，两者不一致会导致
  # 配置和项目识别出现路径冲突。这里统一指向 /headless。
  # -------------------------------------------------------
  if grep -q '^root:.*:/root:' /etc/passwd 2>/dev/null; then
    sed -i 's|^root:\(.*\):/root:|root:\1:/headless:|' /etc/passwd
    echo "[INFO] Fixed root HOME in /etc/passwd: /root -> /headless"
  fi

  # 确保 OpenCode CLI 核心命令行程序存在 (精准锁定版本 1.17.10)
  OPENCODE_TARGET_VERSION="1.17.10"
  INSTALLED_CLI_VER=""
  if [ -x "${OPENCODE_BIN}" ]; then
    INSTALLED_CLI_VER="$("${OPENCODE_BIN}" --version 2>/dev/null || true)"
  fi

  if [ "${INSTALLED_CLI_VER}" != "${OPENCODE_TARGET_VERSION}" ]; then
    echo "[INFO] Installing OpenCode CLI version ${OPENCODE_TARGET_VERSION}..."
    curl -fsSL https://opencode.ai/install | bash -s -- --version "${OPENCODE_TARGET_VERSION}" || echo "[ERROR] Failed to install OpenCode CLI version ${OPENCODE_TARGET_VERSION}"
  else
    echo "[INFO] OpenCode CLI is ready at ${OPENCODE_BIN} (version ${INSTALLED_CLI_VER})."
  fi

  # 软链接 /usr/bin/opencode 指向 CLI 命令行程序
  if [ -x "${OPENCODE_BIN}" ]; then
    ln -sf "${OPENCODE_BIN}" /usr/bin/opencode
    echo "[INFO] Symlinked /usr/bin/opencode -> ${OPENCODE_BIN}"
  fi

  # 配置全局 Git，OpenCode 依赖 Git 提交记录，如果没有身份信息会报错
  git config --global user.email "dev@opencode.local"
  git config --global user.name "OpenCode"
  git config --global init.defaultBranch main

  # 确保 PATH 包含 opencode bin
  export PATH="${OPENCODE_HOME}/bin:${PATH}"

  # 使用 nohup 启动 opencode web 并在后台运行 (明确使用 CLI 二进制文件)
  if [ ! -x "${OPENCODE_BIN}" ]; then
    echo "[WARN] OpenCode CLI executable not found at ${OPENCODE_BIN}; skipping start."
    return 0
  fi

  if pgrep -f "opencode web" >/dev/null 2>&1; then
    echo "[INFO] OpenCode Web UI is already running."
  else
    cd /headless || true
    nohup "${OPENCODE_BIN}" web --hostname 0.0.0.0 --port 4096 >> "${LOG_DIR}/opencode_web.log" 2>&1 &
    echo "[INFO] OpenCode Web UI started with nohup in background."
  fi
}

show_system_info() {
  echo ""
  echo "--- [system_info] ---"
  echo "[INFO] ACTUAL_HOME            : ${ACTUAL_HOME}"
  echo "[INFO] OPENCODE_HOME          : ${OPENCODE_HOME}"
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "[INFO] OS Version             : ${PRETTY_NAME}"
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "[INFO] Python3 Version        : $(python3 --version 2>&1)"
  fi
  if command -v git >/dev/null 2>&1; then
    echo "[INFO] Git Version            : $(git --version 2>&1)"
  fi
}

# 执行顺序
setup_users
setup_packages
show_system_info
setup_ssh
setup_opencode
setup_node

if [ -f /headless/Desktop/config/setup_mcp.py ]; then
  echo ""
  echo "--- [setup_mcp] ---"
  python3 /headless/Desktop/config/setup_mcp.py --skip-validate || echo "[WARN] MCP setup script failed"
else
  echo "[WARN] setup_mcp.py not found; skipping MCP configuration"
fi


echo ""
echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] container-init.sh DONE"
echo "========================================"
