#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# OpenCode 重启脚本
# 用于在配置 MCP 或其他服务后重启 OpenCode

LOG_DIR="/dockerstartup/custom"
LOG_FILE="${LOG_DIR}/opencode_restart.log"

# =====================================
# OpenCode 路径配置 - 在 consol/debian-xfce-vnc 容器中
# =====================================
ACTUAL_HOME="${ACTUAL_HOME:-/headless}"
OPENCODE_HOME="${OPENCODE_HOME:-${ACTUAL_HOME}/.opencode}"
OPENCODE_BIN="${OPENCODE_HOME}/bin/opencode"

mkdir -p "${LOG_DIR}"

echo "========================================"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Restarting OpenCode..."
echo "========================================"

# 1. 停止现有的 opencode 进程
echo "[INFO] Stopping existing OpenCode processes..."
pkill -f "opencode web" || echo "[INFO] No OpenCode process found"

# 等待进程完全停止
sleep 2

# 2. 确认进程已停止
if pgrep -f "opencode web" >/dev/null 2>&1; then
  echo "[WARN] OpenCode still running, force killing..."
  pkill -9 -f "opencode web" || true
  sleep 1
fi

echo "[INFO] OpenCode stopped successfully."

# 3. 重新启动 OpenCode
echo "[INFO] Starting OpenCode with nohup from /headless directory..."

export PATH="${OPENCODE_HOME}/bin:${PATH}"

if ! command -v opencode >/dev/null 2>&1; then
  echo "[ERROR] opencode command not found in PATH"
  exit 1
fi

# 修正 /etc/passwd 中 root 的 HOME（与 container-init.sh 保持一致）
if grep -q '^root:.*:/root:' /etc/passwd 2>/dev/null; then
  sed -i 's|^root:\(.*\):/root:|root:\1:/headless:|' /etc/passwd
  echo "[INFO] Fixed root HOME in /etc/passwd: /root -> /headless"
fi

cd /headless || true
nohup opencode web --hostname 0.0.0.0 --port 4096 >> ${LOG_DIR}/opencode_web.log 2>&1 &
OPENCODE_PID=$!

echo "[INFO] OpenCode started with PID: ${OPENCODE_PID}"

# 4. 等待一下并检查进程是否在运行
sleep 3

if ps -p ${OPENCODE_PID} >/dev/null 2>&1; then
  echo "[INFO] OpenCode is running successfully."
  echo "========================================"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] OpenCode restart DONE"
  echo "========================================"
else
  echo "[ERROR] OpenCode failed to start. Check logs at ${LOG_DIR}/opencode_web.log"
  exit 1
fi
