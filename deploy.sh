#!/usr/bin/env bash
# ==============================================================================
#  Debian Xfce VNC Agent Sandbox Control Panel (Non-.env version)
# ==============================================================================
# This script manages docker compose and provides interactive tools.
# Custom configurations are stored in a private .deploy_config file.
# Works on macOS and Linux.
# ==============================================================================

# Exit codes and safety configurations
IFS=$'\n\t'

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

# AI Model settings (Ollama remote service)
OLLAMA_HOST=http://100.102.149.107:11434
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
  VNC_RESOLUTION="${VNC_RESOLUTION:-1280x720}"
  VNC_PW="${VNC_PW:-1234}"
  OLLAMA_HOST="${OLLAMA_HOST:-http://100.102.149.107:11434}"
  TZ="${TZ:-Asia/Seoul}"
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
  echo -e " OpenCode WebUI:     ${CYAN}http://localhost:${OPENCODE_PORT}${NC}"
  echo -e " Ollama Endpoint:    ${CYAN}${OLLAMA_HOST}${NC}"
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
    echo -e "7) Ollama Host URL       : ${CYAN}${OLLAMA_HOST}${NC}"
    echo -e "8) Container Timezone    : ${CYAN}${TZ}${NC}"
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
        echo -n "Enter Ollama Host URL [current: ${OLLAMA_HOST}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "OLLAMA_HOST" "$input_val"; fi
        ;;
      8)
        echo -n "Enter Timezone (e.g. Asia/Shanghai) [current: ${TZ}]: "
        read -r input_val
        if [ -n "$input_val" ]; then set_config_val "TZ" "$input_val"; fi
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

# --- Run Workspace Initialization Scripts inside Container ---
run_workspace_scripts() {
  if ! is_running; then
    echo -e "${RED}[ERROR] Container is not running. Please start the environment first.${NC}"
    read -n 1 -s -r -p "Press any key to return..."
    return
  fi

  while true; do
    show_banner
    echo -e "${BOLD}--- AI Agent Workspace Init Submenu ---${NC}"
    echo -e "Configure the workspace components inside the running container:\n"
    echo -e "1) Connect & Auto-Configure Ollama (setup_opencode_ollama.sh)"
    echo -e "2) Install MCP Drivers & System Dependencies (setup_mcp.py)"
    echo -e "3) Install OpenCode Web Extensions/Plugins (setup_plugin.py)"
    echo -e "4) Import Agent Skill Definitions (setup_skill.py)"
    echo -e "5) [Run All] Sequential Setup (Ollama -> MCP -> Plugins -> Skill)"
    echo -e "6) Restart OpenCode Service Process (restart_opencode.sh)"
    echo -e "0) Back to Main Menu"
    echo -e "\n================================================================"
    echo -n "Select option [0-6]: "
    read -r init_opt

    case "$init_opt" in
      1)
        echo -e "\n${BLUE}[1/1] Running Ollama auto-configuration...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && bash setup_opencode_ollama.sh"
        read -n 1 -s -r -p "Press any key to continue..."
        ;;
      2)
        echo -e "\n${BLUE}[1/1] Installing MCP dependencies...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && python3 setup_mcp.py"
        read -n 1 -s -r -p "Press any key to continue..."
        ;;
      3)
        echo -e "\n${BLUE}[1/1] Installing OpenCode plugins...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && python3 setup_plugin.py"
        read -n 1 -s -r -p "Press any key to continue..."
        ;;
      4)
        echo -e "\n${BLUE}[1/1] Importing Agent skills...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && python3 setup_skill.py"
        read -n 1 -s -r -p "Press any key to continue..."
        ;;
      5)
        echo -e "\n${GREEN}Starting Sequential Setup Chain...${NC}"
        echo -e "\n${BLUE}[Step 1/4] Running Ollama configuration...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && bash setup_opencode_ollama.sh"
        
        echo -e "\n${BLUE}[Step 2/4] Installing MCP dependencies...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && python3 setup_mcp.py"
        
        echo -e "\n${BLUE}[Step 3/4] Installing OpenCode plugins...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && python3 setup_plugin.py"
        
        echo -e "\n${BLUE}[Step 4/4] Importing Agent skills...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && python3 setup_skill.py"
        
        echo -e "\n${GREEN}[SUCCESS] Sequential initialization completed!${NC}"
        read -n 1 -s -r -p "Press any key to continue..."
        ;;
      6)
        echo -e "\n${BLUE}[1/1] Restarting OpenCode server...${NC}"
        $DOCKER_COMPOSE_CMD exec -it debian-xfce-vnc bash -c "cd /headless/Desktop/config && bash restart_opencode.sh"
        read -n 1 -s -r -p "Press any key to continue..."
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
    echo -e "1) Start/Up Environment        6) Enter Container Shell Console"
    echo -e "2) Stop/Down Environment       7) Edit Config Parameters (.deploy_config)"
    echo -e "3) Restart Environment         8) Full Reset & Clean Volumes"
    echo -e "4) View Container Logs         9) Force Recreate & Start"
    echo -e "5) Run Workspace Init Scripts  10) Force Update from GitHub"
    echo -e "11) Backup & Clean Workspace   0) Exit"
    echo -e "================================================================"
    echo -n "Select option (0-11): "
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
        run_workspace_scripts
        ;;
      6)
        enter_console
        ;;
      7)
        configure_settings
        ;;
      8)
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
      9)
        echo -e "\n${BLUE}Force recreating and spinning up containers...${NC}"
        $DOCKER_COMPOSE_CMD up -d --force-recreate
        echo -e "${GREEN}[OK] Docker Compose force-recreate finished.${NC}"
        sleep 2
        ;;
      10)
        echo -e "\n${RED}${BOLD}[WARNING] This will DISCARD all local changes and pull the latest code from GitHub.${NC}"
        echo -n "Are you sure you want to proceed? (y/N): "
        read -r confirm_pull
        if [[ "$confirm_pull" =~ ^[Yy]$ ]]; then
          echo -e "${BLUE}Force updating from GitHub...${NC}"
          branch_name=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
          git fetch --all
          git reset --hard origin/$branch_name
          echo -e "${GREEN}[OK] Update finished.${NC}"
        else
          echo -e "Update canceled."
        fi
        sleep 2
        ;;
      11)
        echo -e "\n${RED}${BOLD}[WARNING] This will backup and wipe your current 'workspace' directory.${NC}"
        echo -e "Your current workspace will be renamed to 'workspace_<timestamp>.bak'."
        echo -e "A fresh, empty 'workspace' folder will be created in its place."
        echo -n "Type 'yes' to confirm and proceed: "
        read -r confirm_clean
        if [[ "$confirm_clean" == "yes" ]]; then
          timestamp=$(date +%Y%m%d_%H%M%S)
          bak_dir="workspace_${timestamp}.bak"
          echo -e "${BLUE}Moving 'workspace' to '${bak_dir}'...${NC}"
          if [ -d "workspace" ]; then
            mv workspace "$bak_dir"
          fi
          mkdir -p workspace
          echo -e "${GREEN}[OK] Workspace cleaned and backed up.${NC}"
        else
          echo -e "Workspace cleanup canceled."
        fi
        sleep 2
        ;;
      0)
        echo -e "\n${GREEN}Exiting. Good bye!${NC}\n"
        exit 0
        ;;
      *)
        echo -e "${RED}Invalid option! Please enter a choice between 0 and 11.${NC}"
        sleep 1.5
        ;;
    esac
  done
}

# --- Start Entry point ---
check_deps
main_menu
