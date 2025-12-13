#!/bin/bash
#
# OrchestrateOS Remote Install Script (Part 1: Installation)
# Installs dependencies, clones repo, starts services
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/unmistakablecreative/orchestrate-remote-install/main/install_orchestrate.sh | bash -s -- --ngrok-token YOUR_TOKEN --ngrok-domain YOUR_DOMAIN
#
# Or download and run:
#   chmod +x install_orchestrate.sh
#   ./install_orchestrate.sh --ngrok-token YOUR_TOKEN --ngrok-domain YOUR_DOMAIN

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
ORCHESTRATE_HOME="$HOME/Orchestrate Github/orchestrate-jarvis"
GITHUB_REPO="https://github.com/unmistakablecreative/orchestrate-remote-install.git"
NGROK_TOKEN=""
NGROK_DOMAIN=""
FASTAPI_PORT=5001

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ngrok-token)
            NGROK_TOKEN="$2"
            shift 2
            ;;
        --ngrok-domain)
            NGROK_DOMAIN="$2"
            shift 2
            ;;
        --port)
            FASTAPI_PORT="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         OrchestrateOS Remote Install Script                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================
# PHASE 1: HEAVY STUFF FIRST - External downloads that might fail
# ============================================================

# Step 1: Install Claude Code CLI (HEAVY - external download)
echo -e "${YELLOW}[1/8] Installing Claude Code CLI...${NC}"
curl -fsSL https://claude.ai/install.sh | bash

# Source shell profile to get claude command
if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" 2>/dev/null || true
elif [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc" 2>/dev/null || true
fi

# Step 2: Install ngrok if not present (MEDIUM - might need brew/download)
echo -e "${YELLOW}[2/8] Setting up ngrok...${NC}"
if ! command -v ngrok &> /dev/null; then
    echo "Installing ngrok..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install ngrok/ngrok/ngrok
        else
            echo "Installing ngrok manually..."
            curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-amd64.zip -o ngrok.zip
            unzip -o ngrok.zip
            sudo mv ngrok /usr/local/bin/
            rm ngrok.zip
        fi
    else
        # Linux
        curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz | tar xz
        sudo mv ngrok /usr/local/bin/
    fi
fi

# Configure ngrok token if provided
if [ -n "$NGROK_TOKEN" ]; then
    echo "Configuring ngrok auth token..."
    ngrok config add-authtoken "$NGROK_TOKEN"
fi

# ============================================================
# PHASE 2: REPO & DEPENDENCIES
# ============================================================

# Step 3: Clone repo (creates directory automatically)
echo -e "${YELLOW}[3/8] Cloning OrchestrateOS repository...${NC}"
if [ -d "$ORCHESTRATE_HOME" ]; then
    echo "Directory exists, pulling latest changes..."
    cd "$ORCHESTRATE_HOME"
    git pull origin main || true
else
    mkdir -p "$(dirname "$ORCHESTRATE_HOME")"
    git clone "$GITHUB_REPO" "$ORCHESTRATE_HOME"
fi
cd "$ORCHESTRATE_HOME"

# ============================================================
# IMMEDIATELY AFTER CLONE: Domain replacement in template files
# ============================================================
if [ -n "$NGROK_DOMAIN" ]; then
    echo "Configuring template files with domain: $NGROK_DOMAIN"

    # Create safe domain string (replace dots and hyphens with underscores)
    SAFE_DOMAIN=$(echo "$NGROK_DOMAIN" | sed 's/[.-]/_/g')

    # Update openapi_template.yaml - replace $DOMAIN with actual domain
    if [ -f "$ORCHESTRATE_HOME/openapi_template.yaml" ]; then
        sed -i '' "s|\\\$DOMAIN|$NGROK_DOMAIN|g" "$ORCHESTRATE_HOME/openapi_template.yaml" 2>/dev/null || \
        sed "s|\\\$DOMAIN|$NGROK_DOMAIN|g" "$ORCHESTRATE_HOME/openapi_template.yaml" > "$ORCHESTRATE_HOME/openapi_template.yaml.tmp" && \
        mv "$ORCHESTRATE_HOME/openapi_template.yaml.tmp" "$ORCHESTRATE_HOME/openapi_template.yaml"
        echo -e "  ${GREEN}✓${NC} Updated openapi_template.yaml"
    fi

    # Update instructions_template.json - replace ${SAFE_DOMAIN} with underscored version
    if [ -f "$ORCHESTRATE_HOME/instructions_template.json" ]; then
        sed -i '' "s|\${SAFE_DOMAIN}|$SAFE_DOMAIN|g" "$ORCHESTRATE_HOME/instructions_template.json" 2>/dev/null || \
        sed "s|\${SAFE_DOMAIN}|$SAFE_DOMAIN|g" "$ORCHESTRATE_HOME/instructions_template.json" > "$ORCHESTRATE_HOME/instructions_template.json.tmp" && \
        mv "$ORCHESTRATE_HOME/instructions_template.json.tmp" "$ORCHESTRATE_HOME/instructions_template.json"
        echo -e "  ${GREEN}✓${NC} Updated instructions_template.json"
    fi
fi

# Step 4: Install Python dependencies (HEAVY - pip install)
echo -e "${YELLOW}[4/8] Installing Python dependencies...${NC}"
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt --quiet
else
    echo -e "${RED}pip3 not found. Please install Python 3 first.${NC}"
    exit 1
fi

# Step 5: Reset data files for clean install
echo -e "${YELLOW}[5/8] Resetting data files for clean install...${NC}"
mkdir -p "$ORCHESTRATE_HOME/data"
echo "[]" > "$ORCHESTRATE_HOME/data/claude_task_queue.json"
echo "{}" > "$ORCHESTRATE_HOME/data/claude_task_results.json"
echo "{}" > "$ORCHESTRATE_HOME/data/outline_queue.json"

# ============================================================
# PHASE 3: START SERVICES
# ============================================================

# Step 6: Start FastAPI server
echo -e "${YELLOW}[6/8] Starting FastAPI server...${NC}"
cd "$ORCHESTRATE_HOME"

# Kill any existing server
pkill -f "uvicorn jarvis:app" 2>/dev/null || true

# Start server in background
nohup python3 -m uvicorn jarvis:app --host 0.0.0.0 --port $FASTAPI_PORT > /tmp/orchestrate_server.log 2>&1 &
FASTAPI_PID=$!
echo "FastAPI server started with PID: $FASTAPI_PID"

# Wait for server to start
sleep 3

# Step 7: Start ngrok tunnel
echo -e "${YELLOW}[7/8] Starting ngrok tunnel...${NC}"
pkill -f "ngrok http" 2>/dev/null || true

if [ -n "$NGROK_DOMAIN" ]; then
    nohup ngrok http $FASTAPI_PORT --domain="$NGROK_DOMAIN" > /tmp/ngrok.log 2>&1 &
else
    nohup ngrok http $FASTAPI_PORT > /tmp/ngrok.log 2>&1 &
fi
NGROK_PID=$!
echo "ngrok started with PID: $NGROK_PID"

# Wait for ngrok to establish tunnel
sleep 5

# Get ngrok URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; tunnels=json.load(sys.stdin).get('tunnels',[]); print(tunnels[0]['public_url'] if tunnels else 'NOT_AVAILABLE')" 2>/dev/null || echo "NOT_AVAILABLE")

# ============================================================
# PHASE 4: VISUAL CONFIRMATION - Server & ngrok health checks
# ============================================================

echo -e "${YELLOW}[8/8] Running verification checks...${NC}"
echo ""

# Visual confirmation box
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                  SERVICE STATUS CHECK                       ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Server health check
echo -n "  FastAPI Server (localhost:$FASTAPI_PORT)... "
HEALTH_CHECK=$(curl -s "http://localhost:$FASTAPI_PORT/" 2>/dev/null || echo "FAILED")
if echo "$HEALTH_CHECK" | grep -q "online"; then
    echo -e "${GREEN}✓ RUNNING${NC}"
    SERVER_OK=true
else
    echo -e "${RED}✗ NOT RESPONDING${NC}"
    SERVER_OK=false
fi

# ngrok tunnel check
echo -n "  ngrok Tunnel... "
if [ "$NGROK_URL" != "NOT_AVAILABLE" ]; then
    echo -e "${GREEN}✓ ACTIVE${NC}"
    NGROK_OK=true
else
    echo -e "${RED}✗ NOT AVAILABLE${NC}"
    NGROK_OK=false
fi

# Test /supported_actions endpoint
echo -n "  API Endpoint Test... "
ACTIONS_RESPONSE=$(curl -s "http://localhost:$FASTAPI_PORT/supported_actions" 2>/dev/null || echo "FAILED")
if echo "$ACTIONS_RESPONSE" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    echo -e "${GREEN}✓ PASSED${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

echo ""
echo -e "${GREEN}  Server URL:${NC} http://localhost:$FASTAPI_PORT"
echo -e "${GREEN}  Public URL:${NC} $NGROK_URL"
echo ""

if [ "$SERVER_OK" = false ] || [ "$NGROK_OK" = false ]; then
    echo -e "${RED}Some services failed to start. Check logs:${NC}"
    echo "  FastAPI: /tmp/orchestrate_server.log"
    echo "  ngrok: /tmp/ngrok.log"
    echo ""
    read -p "Press ENTER to continue anyway, or Ctrl+C to abort..."
fi

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  INSTALLATION COMPLETE!                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================
# SAVE CONFIG FOR SETUP WIZARD
# ============================================================

# Save ngrok URL and port to config file for setup_wizard.sh
CONFIG_FILE="$ORCHESTRATE_HOME/.install_config"
echo "NGROK_URL=$NGROK_URL" > "$CONFIG_FILE"
echo "FASTAPI_PORT=$FASTAPI_PORT" >> "$CONFIG_FILE"
echo "ORCHESTRATE_HOME=$ORCHESTRATE_HOME" >> "$CONFIG_FILE"

# ============================================================
# LAUNCH SETUP WIZARD IN NEW TERMINAL
# ============================================================

echo -e "${CYAN}Launching setup wizard in new Terminal window...${NC}"
echo ""

# Make setup_wizard.sh executable
chmod +x "$ORCHESTRATE_HOME/setup_wizard.sh" 2>/dev/null || true

# Launch setup wizard in new Terminal window
osascript -e "tell application \"Terminal\" to do script \"cd '$ORCHESTRATE_HOME' && ./setup_wizard.sh\""

echo -e "${GREEN}Setup wizard launched in new window.${NC}"
echo ""
echo "This window will remain open for reference."
echo "Continue setup in the new Terminal window that just opened."
echo ""
