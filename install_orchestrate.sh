#!/bin/bash
#
# OrchestrateOS Remote Install Script
# Autonomous installation for Mac machines
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
# HEAVY STUFF FIRST - External downloads that might fail
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
# REPO & DEPENDENCIES
# ============================================================

# Step 3: Clone repo (creates directory automatically)
echo -e "${YELLOW}[3/7] Cloning OrchestrateOS repository...${NC}"
if [ -d "$ORCHESTRATE_HOME" ]; then
    echo "Directory exists, pulling latest changes..."
    cd "$ORCHESTRATE_HOME"
    git pull origin main || true
else
    git clone "$GITHUB_REPO" "$ORCHESTRATE_HOME"
fi
cd "$ORCHESTRATE_HOME"

# Step 4: Install Python dependencies (HEAVY - pip install)
echo -e "${YELLOW}[4/7] Installing Python dependencies...${NC}"
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt --quiet
else
    echo -e "${RED}pip3 not found. Please install Python 3 first.${NC}"
    exit 1
fi

# Step 5: Reset data files for clean install
echo -e "${YELLOW}[5/7] Resetting data files for clean install...${NC}"
mkdir -p "$ORCHESTRATE_HOME/data"
echo "[]" > "$ORCHESTRATE_HOME/data/claude_task_queue.json"
echo "{}" > "$ORCHESTRATE_HOME/data/claude_task_results.json"
echo "{}" > "$ORCHESTRATE_HOME/data/outline_queue.json"

# ============================================================
# START SERVICES
# ============================================================

# Step 6: Start FastAPI server
echo -e "${YELLOW}[6/7] Starting FastAPI server...${NC}"
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
echo -e "${YELLOW}[7/7] Starting ngrok tunnel...${NC}"
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

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  INSTALLATION COMPLETE!                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}FastAPI Server:${NC} http://localhost:$FASTAPI_PORT"
echo -e "${GREEN}ngrok URL:${NC} $NGROK_URL"
echo ""

# Verification tests
echo -e "${YELLOW}Running verification tests...${NC}"
echo ""

# Test 1: Check /supported_actions endpoint
echo -n "Testing /supported_actions endpoint... "
ACTIONS_RESPONSE=$(curl -s "http://localhost:$FASTAPI_PORT/supported_actions" 2>/dev/null || echo "FAILED")
if echo "$ACTIONS_RESPONSE" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
    echo -e "${GREEN}✓ PASSED${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

# Test 2: Execute a simple JSON manager task
echo -n "Testing /execute_task endpoint... "
EXEC_RESPONSE=$(curl -s -X POST "http://localhost:$FASTAPI_PORT/execute_task" \
    -H "Content-Type: application/json" \
    -d '{"tool_name": "json_manager", "action": "list_files", "params": {}}' 2>/dev/null || echo "FAILED")
if echo "$EXEC_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if data.get('status') else 1)" 2>/dev/null; then
    echo -e "${GREEN}✓ PASSED${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

echo ""
echo -e "${GREEN}Installation and verification complete!${NC}"
echo ""
echo "To use OrchestrateOS:"
echo "  - Send tasks to: $NGROK_URL/execute_task"
echo "  - Check status at: $NGROK_URL/supported_actions"
echo ""
echo "Logs:"
echo "  - FastAPI: /tmp/orchestrate_server.log"
echo "  - ngrok: /tmp/ngrok.log"
echo ""
echo "To stop services:"
echo "  pkill -f 'uvicorn jarvis:app'"
echo "  pkill -f 'ngrok http'"
