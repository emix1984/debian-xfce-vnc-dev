#!/bin/bash
set -e

LOG_FILE="/dockerstartup/custom/init.log"
LOG_DIR="/dockerstartup/custom"

mkdir -p "${LOG_DIR}"

exec > >(tee -a "${LOG_FILE}") 2>&1
TEEPID=$!
echo "${TEEPID}" > /tmp/.init_tee.pid

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] init.sh START"
echo "========================================"

setup_users() {
  echo ""
  echo "--- [setup_users] ---"

  echo "root:1234" | chpasswd
  echo "[INFO] Root password set."

  if ! id default >/dev/null 2>&1; then
    useradd -m -s /bin/bash default
    echo "[INFO] User 'default' created."
  else
    echo "[INFO] User 'default' already exists."
  fi

  echo "default:1234" | chpasswd
  echo "[INFO] Default password set."

  usermod -aG sudo default
  echo "[INFO] Default user added to sudo group."

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
    apt-get update -qq && apt-get install -y -qq openssh-server
    echo "[INFO] openssh-server installed."
  else
    echo "[INFO] openssh-server already installed."
  fi

  mkdir -p /var/run/sshd

  if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    echo "[INFO] Generating SSH host keys..."
    dpkg-reconfigure openssh-server
    echo "[INFO] SSH host keys generated."
  else
    echo "[INFO] SSH host keys already exist."
  fi

  sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
  sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

  if grep -q "PermitRootLogin yes" /etc/ssh/sshd_config && \
     grep -q "PasswordAuthentication yes" /etc/ssh/sshd_config; then
    echo "[INFO] SSH config updated successfully."
  else
    echo "[ERROR] SSH config update FAILED."
    exit 1
  fi

  if ! pgrep -x sshd >/dev/null; then
    /usr/sbin/sshd
    echo "[INFO] SSH service started."
  else
    echo "[INFO] SSH service already running."
  fi
}

setup_packages() {
  echo ""
  echo "--- [setup_packages] ---"

  # 你要安装的包列表，可以随时增减
  PACKAGES=(
    git
    curl
    wget
    nano
    unzip
    tmux
    geany
    # 在这里继续添加其他需要的包，比如 opencode
    # curl -fsSL https://opencode.ai/install | bash
  )

  MISSING=()
  for pkg in "${PACKAGES[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      MISSING+=("$pkg")
    fi
  done

  if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[INFO] Installing missing packages: ${MISSING[*]}"
    apt-get update -qq && apt-get install -y -qq "${MISSING[@]}"
  else
    echo "[INFO] All packages already installed."
  fi
}

setup_users
setup_ssh
setup_packages

echo ""
echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] init.sh DONE"
echo "========================================"