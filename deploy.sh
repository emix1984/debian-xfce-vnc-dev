#!/usr/bin/env bash
# ==============================================================================
#  Debian Xfce VNC Agent Sandbox Control Panel (Non-.env version)
# ==============================================================================
# This script manages docker compose and provides interactive tools.
# Custom configurations are stored in a private .deploy_config file.
# Works on macOS and Linux.
# ==============================================================================

# Exit codes and safety configurations
# Color definitions
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

CONFIG_FILE=".deploy_config"

# --- Print Header Banner ---
show_banner() {
  clear
  echo -e "${CYAN}================================================================${NC}"
  echo -e "${CYAN} ${BOLD}Debian Xfce VNC Agent Workstation - Control Panel${NC}"
  echo -e "${CYAN}================================================================${NC}"
}

# --- Pre-flight Checks ---
check_deps() {
  if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Docker is not installed. Please install Docker first.${NC}"
    exit 1
  fi

  if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}[ERROR] Docker daemon is not running. Please start Docker Desktop/Daemon.${NC}"
    exit 1
  fi

  if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
  elif docker-compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker-compose"
  else
    echo -e "${RED}[ERROR] Docker Compose plugin or command (docker compose / docker-compose) not found.${NC}"
    exit 1
  fi

  # Auto-cleanup standard .env file if it exists to prevent docker compose from reading it directly
  if [ -f ".env" ]; then
    echo -e "${YELLOW}[INFO] Cleaning up standard .env file to prevent direct docker compose overrides...${NC}"
    rm -f ".env"
  fi
}

# --- Load Environment Settings ---
load_env() {
  # If .deploy_config does not exist, create it with default values
  if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}[INFO] Configuration file ($CONFIG_FILE) not found. Creating with default values...${NC}"
    cat <<EOF > "$CONFIG_FILE"
# ==============================================================================
# Debian Xfce VNC Workstation Private Configurations
# (Managed by deploy.sh, direct docker compose commands will bypass these)
# ==============================================================================

# External port mapping settings
VNC_PORT=5901
NOVNC_PORT=6901
SSH_PORT=2222
OPENCODE_PORT=4096

# Container internal system settings
VNC_RESOLUTION=1280x720
VNC_PW=1234
TZ=Asia/Seoul
OPENCODE_WEBUI_TITLE=OpenCode

# Agent Browser integration settings
AGENT_BROWSER_VERSION=v0.33.2

EOF
    echo -e "${GREEN}[OK] Private configuration file ($CONFIG_FILE) created.${NC}"
    sleep 1
  fi

  # Parse existing variables and export them
  while IFS= read -r line || [ -n "$line" ]; do
    # Remove leading/trailing whitespace
    line=$(echo "$line" | xargs)
    # Ignore comments and empty lines
    if [[ ! "$line" =~ ^# ]] && [[ "$line" =~ = ]]; then
      local key=$(echo "$line" | cut -d'=' -f1 | xargs)
      local val=$(echo "$line" | cut -d'=' -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
      export "$key"="$val"
    fi
  done < "$CONFIG_FILE"

  # Fallbacks for variables in case they are missing in config
  VNC_PORT="${VNC_PORT:-5901}"
  NOVNC_PORT="${NOVNC_PORT:-6901}"
  SSH_PORT="${SSH_PORT:-2222}"
  OPENCODE_PORT="${OPENCODE_PORT:-4096}"
  VNC_RESOLUTION="${VNC_RESOLUTION:-1280x1024}"
  VNC_PW="${VNC_PW:-1234}"
  TZ="${TZ:-Asia/Seoul}"
  OPENCODE_WEBUI_TITLE="${OPENCODE_WEBUI_TITLE:-OpenCode}"
}

# --- Save Single Parameter ---
set_config_val() {
  local key=$1
  local val=$2
  
  if [ ! -f "$CONFIG_FILE" ]; then
    touch "$CONFIG_FILE"
  fi

  if grep -q "^${key}=" "$CONFIG_FILE"; then
    # Escape special characters for sed (specifically '/' and '&')
    local escaped_val=$(echo "$val" | sed -e 's/[\/&]/\\&/g')
    # Use backup extension for cross-platform compatibility with macOS and Linux sed
    sed -i.bak -e "s/^${key}=.*/${key}=${escaped_val}/" "$CONFIG_FILE" && rm -f "${CONFIG_FILE}.bak"
  else
    echo "${key}=${val}" >> "$CONFIG_FILE"
  fi
}

# --- Check Container Running Status ---
get_container_status() {
  local container_name="debian-xfce-vnc"
  local status=$(docker ps -a --filter "name=${container_name}" --format '{{.Status}}')
  if [ -z "$status" ]; then
    echo -e "${RED}Not Created${NC}"
  elif echo "$status" | grep -q "Up"; then
    echo -e "${GREEN}Running (${status})${NC}"
  else
    echo -e "${YELLOW}Stopped (${status})${NC}"
  fi
}

is_running() {
  local container_name="debian-xfce-vnc"
  docker ps --filter "name=${container_name}" --format '{{.Status}}' | grep -q "Up"
}

# --- Dashboard Display ---
show_dashboard() {
  local status_str=$(get_container_status)
  echo -e "Container Status: ${status_str}"
  echo -e "\n${BOLD}--- Current Access Details ---${NC}"
  echo -e " VNC Desktop client: ${CYAN}vnc://localhost:${VNC_PORT}${NC}"
  echo -e " noVNC Browser:      ${CYAN}http://localhost:${NOVNC_PORT}${NC}"
  echo -e " SSH Console login:  ${CYAN}ssh default@localhost -p ${SSH_PORT}${NC} (Password: ${BOLD}${VNC_PW}${NC})"
  echo -e " OpenCode WebUI:     ${CYAN}http://localhost:${OPENCODE_PORT}${NC} (Title: ${BOLD}${OPENCODE_WEBUI_TITLE}${NC})"
  echo -e " Custom Ports:       ${CYAN}9980-9990${NC} (后期特殊用途)"
}

# --- Edit Parameter Menu ---
configure_settings() {
  while true; do
    load_env
    show_banner
    echo -e "${BOLD}--- Parameter Configuration Menu ---${NC}\n"
    echo -e "1) VNC Desktop Port      : ${CYAN}${VNC_PORT}${NC}"
    echo -e "2) noVNC Browser Port    : ${CYAN}${NOVNC_PORT}${NC}"
    echo -e "3) SSH Console Port      : ${CYAN}${SSH_PORT}${NC}"
    echo -e "4) OpenCode WebUI Port   : ${CYAN}${OPENCODE_PORT}${NC}"
    echo -e "5) VNC Desktop Resolution: ${CYAN}${VNC_RESOLUTION}${NC}"
    echo -e "6) VNC/SSH Password      : ${CYAN}${VNC_PW}${NC}"
    echo -e "7) Container Timezone    : ${CYAN}${TZ}${NC}"
    echo -e "8) OpenCode WebUI Title  : ${CYAN}${OPENCODE_WEBUI_TITLE}${NC}"
    echo -e "0) Back to Main Menu"
    echo -e "\n================================================================"
    echo -n "Select parameter to modify [0-8]: "
    read -r config_opt

    case "$config_opt" in
      1)
        echo -n "Enter VNC Port [current: ${VNC_PORT}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "VNC_PORT" "$input_val"; fi
        ;;
      2)
        echo -n "Enter noVNC Browser Port [current: ${NOVNC_PORT}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "NOVNC_PORT" "$input_val"; fi
        ;;
      3)
        echo -n "Enter SSH Port [current: ${SSH_PORT}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "SSH_PORT" "$input_val"; fi
        ;;
      4)
        echo -n "Enter OpenCode WebUI Port [current: ${OPENCODE_PORT}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "OPENCODE_PORT" "$input_val"; fi
        ;;
      5)
        echo -n "Enter VNC Desktop Resolution (e.g. 1920x1080) [current: ${VNC_RESOLUTION}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "VNC_RESOLUTION" "$input_val"; fi
        ;;
      6)
        echo -n "Enter VNC/SSH password [current: ${VNC_PW}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "VNC_PW" "$input_val"; fi
        ;;
      7)
        echo -n "Enter Timezone (e.g. Asia/Shanghai) [current: ${TZ}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "TZ" "$input_val"; fi
        ;;
      8)
        echo -n "Enter OpenCode WebUI Head Title [current: ${OPENCODE_WEBUI_TITLE}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "OPENCODE_WEBUI_TITLE" "$input_val"; fi
        ;;
      0)
        break
        ;;
      *)
        echo -e "${RED}Invalid option!${NC}"
        sleep 1
        ;;
    esac
  done
}



# --- Enter Container Bash Console ---
enter_console() {
  if ! is_running; then
    echo -e "${RED}[ERROR] Container is not running. Please start the environment first.${NC}"
    read -n 1 -s -r -p "Press any key to return..."
    return
  fi

  echo -e "\n${BOLD}Attach Console Session:${NC}"
  echo -e "1) Log in as ${BOLD}root${NC} (Privileged access)"
  echo -e "2) Log in as ${BOLD}default${NC} (Standard user, has sudo access)"
  echo -e "0) Back"
  echo -n "Enter console choice: "
  read -r shell_user

  case "$shell_user" in
    1)
      echo -e "${GREEN}Attaching container shell as root...${NC}"
      $DOCKER_COMPOSE_CMD exec -it -u root debian-xfce-vnc bash
      ;;
    2)
      echo -e "${GREEN}Attaching container shell as default user...${NC}"
      $DOCKER_COMPOSE_CMD exec -it -u default debian-xfce-vnc bash
      ;;
    0)
      return
      ;;
    *)
      echo -e "${RED}Invalid choice!${NC}"
      sleep 1
      ;;
  esac
}

# --- Main Interaction Logic ---
main_menu() {
  while true; do
    load_env
    show_banner
    show_dashboard
    
    echo -e "\n${BOLD}--- Controls & Options ---${NC}"
    echo -e "1) Start/Up Environment        6) Edit Config Parameters (.deploy_config)"
    echo -e "2) Stop/Down Environment       7) Full Reset & Clean Volumes"
    echo -e "3) Restart Environment         8) Force Recreate & Start"
    echo -e "4) View Container Logs         9) Force Update from GitHub"
    echo -e "5) Enter Container Shell       10) View Environment & Paths"
    echo -e "0) Exit"
    echo -e "================================================================"
    echo -n "Select option (0-10): "
    read -r menu_opt

    case "$menu_opt" in
      1)
        echo -e "\n${BLUE}Spinning up containers...${NC}"
        $DOCKER_COMPOSE_CMD up -d
        echo -e "${GREEN}[OK] Docker Compose up finished.${NC}"
        sleep 2
        ;;
      2)
        echo -e "\n${BLUE}Stopping container services...${NC}"
        $DOCKER_COMPOSE_CMD down
        echo -e "${GREEN}[OK] Docker Compose down finished.${NC}"
        sleep 2
        ;;
      3)
        echo -e "\n${BLUE}Restarting containers...${NC}"
        $DOCKER_COMPOSE_CMD restart
        echo -e "${GREEN}[OK] Docker Compose restart finished.${NC}"
        sleep 2
        ;;
      4)
        echo -e "\n${BLUE}Streaming logs (Press Ctrl+C to exit log stream)...${NC}"
        $DOCKER_COMPOSE_CMD logs -f
        ;;
      5)
        enter_console
        ;;
      6)
        configure_settings
        ;;
      7)
        echo -e "\n${RED}${BOLD}[WARNING] This will stop the containers and delete all named volumes.${NC}"
        echo -n "Are you sure you want to proceed? (y/N): "
        read -r confirm_reset
        if [[ "$confirm_reset" =~ ^[Yy]$ ]]; then
          echo -e "${BLUE}Cleaning up resources and volumes...${NC}"
          $DOCKER_COMPOSE_CMD down -v
          echo -e "${GREEN}[OK] Clean finished.${NC}"
        else
          echo -e "Cleanup canceled."
        fi
        sleep 2
        ;;
      8)
        echo -e "\n${BLUE}Force recreating and spinning up containers...${NC}"
        $DOCKER_COMPOSE_CMD up -d --force-recreate
        echo -e "${GREEN}[OK] Docker Compose force-recreate finished.${NC}"
        sleep 2
        ;;
      9)
        echo -e "\n${YELLOW}${BOLD}Check remote vs local before updating${NC}"
        echo -n "Fetch remote and show summary? (y/N): "
        read -r confirm_fetch
        if [[ ! "$confirm_fetch" =~ ^[Yy]$ ]]; then
          echo -e "Canceled remote check."
          sleep 1
          break
        fi

        # Ensure we are in a git repo
        if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
          echo -e "${RED}[ERROR] Current directory is not a git repository. Cannot check updates.${NC}"
          sleep 2
          break
        fi

        branch_name=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
        echo -e "${BLUE}Fetching remote refs...${NC}"
        git fetch --all --prune

        # compare counts: origin only / local only
        counts=$(git rev-list --left-right --count origin/${branch_name}...${branch_name} 2>/dev/null || true)
        if [ -z "$counts" ]; then
          echo -e "${YELLOW}[WARN] Could not determine remote branch origin/${branch_name}. Ensure remote exists.${NC}"
          sleep 2
          break
        fi
        remote_only=$(echo "$counts" | awk '{print $1}')
        local_only=$(echo "$counts" | awk '{print $2}')

        echo -e "\n${BOLD}Branch:${NC} ${branch_name}    ${BOLD}Remote commits ahead:${NC} ${remote_only}    ${BOLD}Local commits ahead:${NC} ${local_only}\n"

        if [ "$remote_only" -gt 0 ]; then
          echo -e "${BLUE}Commits on remote not present locally:${NC}"
          git --no-pager log --oneline ${branch_name}..origin/${branch_name} | sed -n '1,20p'
          echo ""
          echo -e "${BLUE}Summary of changed files (remote -> local):${NC}"
          git --no-pager diff --stat ${branch_name}..origin/${branch_name} | sed -n '1,40p'
        else
          echo -e "${GREEN}Remote has no new commits compared to local.${NC}"
        fi

        echo ""
        echo -e "${YELLOW}Important: This update flow will NOT delete your workspace folder (/headless/Desktop/workspace) or its files.${NC}"
        echo -e "If you have uncommitted work, consider stashing or backing up the workspace before applying updates."
        echo ""
        echo "Choose update action:"
        echo "  1) Fast-forward only (safe, will fail if non-fast-forward)"
        echo "  2) Merge (git pull, may create merge commit)"
        echo "  3) Rebase (git pull --rebase)"
        echo "  4) Stash local changes, then pull (safe for local edits)"
        echo "  5) Show full diff (dry-run) and abort"
        echo "  0) Cancel"
        echo -n "Select [0-5]: "
        read -r upd_opt

        case "$upd_opt" in
          1)
            echo -e "${BLUE}Attempting fast-forward pull...${NC}"
            if git pull --ff-only origin ${branch_name}; then
              echo -e "${GREEN}[OK] Fast-forward applied.${NC}"
            else
              echo -e "${RED}[ERROR] Fast-forward failed (non-fast-forward). Consider option 2/3 or stashing local changes.${NC}"
            fi
            ;;
          2)
            echo -e "${BLUE}Merging remote changes (git pull)...${NC}"
            if git pull --no-rebase origin ${branch_name}; then
              echo -e "${GREEN}[OK] Merge completed.${NC}"
            else
              echo -e "${RED}[ERROR] Merge failed. Resolve conflicts manually.${NC}"
            fi
            ;;
          3)
            echo -e "${BLUE}Rebasing local commits onto remote (git pull --rebase)...${NC}"
            if git pull --rebase origin ${branch_name}; then
              echo -e "${GREEN}[OK] Rebase completed.${NC}"
            else
              echo -e "${RED}[ERROR] Rebase failed. Resolve conflicts manually.${NC}"
            fi
            ;;
          4)
            echo -e "${BLUE}Stashing local changes and pulling...${NC}"
            stash_ref=$(git stash push -m "pre-update-$(date -Iseconds)" 2>/dev/null || true)
            if [ -n "$stash_ref" ]; then
              echo -e "${GREEN}[OK] Local changes stashed: ${stash_ref}${NC}"
            else
              echo -e "${YELLOW}[INFO] No local changes to stash or stash failed.${NC}"
            fi
            if git pull origin ${branch_name}; then
              echo -e "${GREEN}[OK] Pull completed.${NC}"
              echo -e "${YELLOW}If you stashed changes you can inspect or apply them with: git stash list / git stash pop${NC}"
            else
              echo -e "${RED}[ERROR] Pull failed after stash. Check repository state.${NC}"
            fi
            ;;
          5)
            echo -e "${BLUE}Showing full diff (remote -> local). This is a dry-run.${NC}"
            git --no-pager diff ${branch_name}..origin/${branch_name} | sed -n '1,200p'
            echo -e "\n${YELLOW}Dry-run complete. No changes applied.${NC}"
            ;;
          0|*)
            echo -e "Update canceled. No changes made to repository or workspace.";
            ;;
        esac

        echo ""
        sleep 2
        ;;
      10)
        if ! is_running; then
          echo -e "\n${RED}[ERROR] Container is not running. Please start the environment first to view dynamic system info.${NC}"
        else
          echo -e "\n${BOLD}--- Dynamic System Info (from inside container) ---${NC}"
          $DOCKER_COMPOSE_CMD exec -T debian-xfce-vnc bash -c '
            echo -e "\033[0;36mOS Version:\033[0m        " $(cat /etc/os-release | grep PRETTY_NAME | cut -d "=" -f 2 | tr -d "\"")
            echo -e "\033[0;36mPython Version:\033[0m    " $(python3 --version 2>&1)
            echo -e "\033[0;36mOpenCode Version:\033[0m  " $(opencode --version 2>/dev/null || echo "Not installed or not in PATH")
          '
        fi
        
        echo -e "\n${BOLD}--- Default Configuration Paths ---${NC}"
        echo -e "${CYAN}Container User Home:${NC}     /headless"
        echo -e "${CYAN}OpenCode Binary Path:${NC}    /usr/local/bin/opencode"
        echo -e "${CYAN}OpenCode Config Dir:${NC}     /headless/.config/opencode/"
        echo -e "${CYAN}OpenCode App Data:${NC}       /headless/.local/share/opencode/"
        echo -e "${CYAN}Host Config Mount:${NC}       /headless/Desktop/config/"
        echo -e "${CYAN}Host Workspace Mount:${NC}    /headless/Desktop/workspace/"
        
        echo ""
        read -n 1 -s -r -p "Press any key to return..."
        ;;
      0)
        echo -e "\n${GREEN}Exiting. Good bye!${NC}\n"
        exit 0
        ;;
      *)
        echo -e "${RED}Invalid option! Please enter a choice between 0 and 10.${NC}"
        sleep 1.5
        ;;
    esac
  done
}

# --- Start Entry point ---
check_deps
main_menu
