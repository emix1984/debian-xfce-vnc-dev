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

setup_opencode() {
  echo ""
  echo "--- [setup_opencode] ---"

  if [ ! -x "${OPENCODE_BIN}" ]; then
    echo "[INFO] Installing OpenCode as root..."
    curl -fsSL https://opencode.ai/install | bash || echo "[WARN] OpenCode install script returned non-zero"
    echo "[INFO] OpenCode installation attempted as root."
  else
    echo "[INFO] OpenCode is already installed for root."
  fi

  # 确保 PATH 包含 opencode
  export PATH="${OPENCODE_HOME}/bin:${PATH}"

  # 不再对整个 ${LOG_DIR} 执行 chown -R，因为 container-init.sh 是只读挂载的，会报错
  # 如果需要可以只 chown log 文件： chown root:root "${LOG_DIR}/opencode_web.log" || true

  # 使用 nohup 启动 opencode web 并在后台运行
  if ! command -v opencode >/dev/null 2>&1; then
    echo "[WARN] opencode not found in PATH; skipping start."
    return 0
  fi

  if pgrep -f "opencode web" >/dev/null 2>&1; then
    echo "[INFO] OpenCode Web UI is already running."
  else
    (
      cd /headless/Desktop/workspace
      export OPENCODE_HOME="/headless/Desktop/workspace/.opencode"
      export OPENCODE_CONFIG_DIR="/headless/Desktop/workspace/.opencode"
      nohup opencode web --hostname 0.0.0.0 --port 4096 >> "${LOG_DIR}/opencode_web.log" 2>&1 &
    )
    echo "[INFO] OpenCode Web UI started with nohup in background from workspace directory."
  fi
}

# 执行顺序
setup_users
setup_packages
setup_ssh
setup_opencode

echo ""
echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] container-init.sh DONE"
echo "========================================"
