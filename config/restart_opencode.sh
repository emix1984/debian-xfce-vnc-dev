#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# OpenCode 重启与升级维护脚本
# 支持模块化执行：版本检查升级、标题补丁、环境就绪检测、优雅启停等

LOG_DIR="/dockerstartup/custom"
LOG_FILE="${LOG_DIR}/opencode_restart.log"

# =====================================
# 1. 基础环境与全局变量定义
# =====================================
init_env() {
  export ACTUAL_HOME="${ACTUAL_HOME:-/headless}"
  export HOME="${ACTUAL_HOME}"
  export OPENCODE_SERVER_USERNAME="${OPENCODE_SERVER_USERNAME:-opencode}"
  export OPENCODE_SERVER_PASSWORD="${OPENCODE_SERVER_PASSWORD:-opencode}"
  export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${ACTUAL_HOME}/.config}"
  export OPENCODE_HOME="${OPENCODE_HOME:-${ACTUAL_HOME}/.opencode}"
  export OPENCODE_BIN="${OPENCODE_HOME}/bin/opencode"
  export PATH="${OPENCODE_HOME}/bin:${PATH}"
  mkdir -p "${LOG_DIR}"
}

log_info() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*"
}

log_warn() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $*"
}

log_error() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*"
}

# =====================================
# 2. 进程管理模块：优雅终止运行中的服务
# =====================================
stop_opencode() {
  log_info "Stopping existing OpenCode processes..."
  pkill -f "opencode (web|serve)" || log_info "No active OpenCode process found."

  # 等待进程完全退出
  sleep 2

  if pgrep -f "opencode (web|serve)" >/dev/null 2>&1; then
    log_warn "OpenCode process still running, sending SIGKILL..."
    pkill -9 -f "opencode (web|serve)" || true
    sleep 1
  fi

  if tmux has-session -t opencode_web >/dev/null 2>&1; then
    log_info "Terminating existing tmux session 'opencode_web'..."
    tmux kill-session -t opencode_web || true
  fi

  log_info "OpenCode services stopped cleanly."
}

# =====================================
# 3. 升级维护模块：自动检测并升级 OpenCode (双保险机制)
# =====================================
upgrade_opencode() {
  # 可通过设置 OPENCODE_AUTO_UPGRADE=false 跳过升级
  if [ "${OPENCODE_AUTO_UPGRADE:-true}" = "false" ]; then
    log_info "OPENCODE_AUTO_UPGRADE is set to false; skipping upgrade check."
    return 0
  fi

  local current_ver="none"
  if [ -x "${OPENCODE_BIN}" ]; then
    current_ver="$("${OPENCODE_BIN}" --version 2>/dev/null || echo "unknown")"
    current_ver="${current_ver##* }"
  fi
  log_info "Current OpenCode version: ${current_ver}"

  local upgraded=0

  # --- 第一重保险：优先尝试 CLI 原生 upgrade / update 指令 ---
  if [ -x "${OPENCODE_BIN}" ]; then
    log_info "[保险 1/2] Attempting native CLI upgrade via '${OPENCODE_BIN} upgrade'..."
    if "${OPENCODE_BIN}" upgrade 2>&1 | tee -a "${LOG_FILE}"; then
      upgraded=1
      log_info "Native CLI upgrade command succeeded."
    elif "${OPENCODE_BIN}" update 2>&1 | tee -a "${LOG_FILE}"; then
      upgraded=1
      log_info "Native CLI update command succeeded."
    else
      log_warn "Native CLI upgrade/update returned non-zero, triggering fallback insurance..."
    fi
  fi

  # --- 第二重保险：当原生更新失败、CLI损坏或缺失时，通过官方安装脚本兜底 ---
  if [ "${upgraded}" -eq 0 ]; then
    log_info "[保险 2/2] Fallback: Fetching latest installer from https://opencode.ai/v2/install..."
    if curl -fsSL https://opencode.ai/v2/install | bash -s -- --no-modify-path; then
      upgraded=1
      log_info "Fallback installer completed successfully."
    else
      log_warn "Fallback installer also failed (possibly offline or network issue); proceeding with existing binary."
    fi
  fi

  # --- 校验并更新软链接与版本信息 ---
  local new_ver="unknown"
  if [ -x "${OPENCODE_BIN}" ]; then
    new_ver="$("${OPENCODE_BIN}" --version 2>/dev/null || echo "unknown")"
    new_ver="${new_ver##* }"
    ln -sf "${OPENCODE_BIN}" /usr/bin/opencode || true
  fi

  if [ "${current_ver}" != "${new_ver}" ] && [ "${new_ver}" != "unknown" ]; then
    log_info "OpenCode successfully upgraded: ${current_ver} -> ${new_ver}"
  else
    log_info "OpenCode is ready at version: ${new_ver}"
  fi
}

# =====================================
# 4. 环境补丁与工作区准备模块
# =====================================
prepare_environment() {
  # 修正 /etc/passwd 中 root 的 HOME 目录一致性
  if grep -q '^root:.*:/root:' /etc/passwd 2>/dev/null; then
    sed -i 's|^root:\(.*\):/root:|root:\1:/headless:|' /etc/passwd || true
    log_info "Fixed root HOME in /etc/passwd: /root -> /headless"
  fi

  # 软链接确保全局 PATH 随时可用
  if [ -x "${OPENCODE_BIN}" ]; then
    ln -sf "${OPENCODE_BIN}" /usr/bin/opencode || true
  fi

  # 检查必要指令
  if ! command -v "${OPENCODE_BIN}" >/dev/null 2>&1 && ! command -v opencode >/dev/null 2>&1; then
    log_error "OpenCode CLI binary not found at ${OPENCODE_BIN}"
    exit 1
  fi

  if ! command -v tmux >/dev/null 2>&1; then
    log_error "tmux is not installed; cannot start OpenCode background session."
    exit 1
  fi

  # 准备并初始化隔离的工作区目录
  local workspace_dir="${ACTUAL_HOME}/Desktop/workspace"
  mkdir -p "${workspace_dir}/.opencode/skills" "${workspace_dir}/.opencode/plugins"

  if [ ! -d "${workspace_dir}/.git" ]; then
    git -C "${workspace_dir}" init -q || true
    log_info "Initialized git repository in workspace."
  fi

  if [ ! -f "${workspace_dir}/.gitignore" ]; then
    cat << 'EOF' > "${workspace_dir}/.gitignore"
node_modules/
.cache/
*.log
.DS_Store
dist/
build/
EOF
    log_info "Initialized workspace .gitignore"
  fi

  # 应用 WebUI 自定义标题补丁
  local title_script="${ACTUAL_HOME}/Desktop/config/setup_webui_title.sh"
  if [ -f "${title_script}" ]; then
    log_info "Applying WebUI Title patch..."
    python3 "${title_script}" || log_warn "WebUI Title patch returned non-zero."
  fi
}

# =====================================
# 5. 服务启动模块：使用 tmux 拉起并验证
# =====================================
start_opencode() {
  local workspace_dir="${ACTUAL_HOME}/Desktop/workspace"
  cd "${workspace_dir}" || true

  local extra_args=()
  if [ -n "${OPENCODE_WEBUI_EXTRA_ARGS:-}" ]; then
    extra_args+=( ${OPENCODE_WEBUI_EXTRA_ARGS} )
  fi
  if [ "${OPENCODE_WEBUI_MDNS:-false}" = "true" ]; then
    extra_args+=( --mdns )
  fi

  log_info "Launching OpenCode server on port 4096 via tmux session 'opencode_web'..."
  tmux new-session -d -s opencode_web bash -c "${OPENCODE_BIN} serve --hostname 0.0.0.0 --port 4096 ${extra_args[*]:-} >> \"${LOG_DIR}/opencode_web.log\" 2>&1"

  # 等待启动并做存活检查
  sleep 3
  if tmux has-session -t opencode_web >/dev/null 2>&1; then
    local active_ver="$("${OPENCODE_BIN}" --version 2>/dev/null || echo "v2")"
    log_info "OpenCode (${active_ver}) is running smoothly in tmux session 'opencode_web'!"
  else
    log_error "OpenCode failed to start in tmux. Please check ${LOG_DIR}/opencode_web.log"
    exit 1
  fi
}

# =====================================
# 6. 主执行流程与参数分发（支持模块化扩展）
# =====================================
main() {
  init_env

  local action="${1:-restart}"

  echo "========================================"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] OpenCode Service Controller [Action: ${action}]"
  echo "========================================"

  case "${action}" in
    upgrade)
      # 单独升级
      stop_opencode
      upgrade_opencode
      prepare_environment
      start_opencode
      ;;
    restart)
      # 默认重启流程：支持自动更新升级后热重启
      stop_opencode
      upgrade_opencode
      prepare_environment
      start_opencode
      ;;
    quick-restart)
      # 快速重启，不检查升级
      OPENCODE_AUTO_UPGRADE=false
      stop_opencode
      prepare_environment
      start_opencode
      ;;
    stop)
      stop_opencode
      ;;
    start)
      prepare_environment
      start_opencode
      ;;
    status)
      if tmux has-session -t opencode_web >/dev/null 2>&1; then
        local ver="$("${OPENCODE_BIN}" --version 2>/dev/null || echo "unknown")"
        echo "[INFO] OpenCode is RUNNING (Version: ${ver})"
      else
        echo "[INFO] OpenCode is STOPPED"
      fi
      ;;
    *)
      echo "Usage: $0 [restart|upgrade|quick-restart|start|stop|status]"
      exit 1
      ;;
  esac

  echo "========================================"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] OpenCode [${action}] completed successfully."
  echo "========================================"
}

main "$@"
