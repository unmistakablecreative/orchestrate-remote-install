#!/bin/bash
#
# OrchestrateOS Remote Install Script (Consolidated)
# Autonomous installation + Setup Wizard for Mac machines
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
# PHASE 5: CLAUDE AUTHENTICATION
# ============================================================

clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🔐 Claude Code Authentication${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Claude Code needs to be authenticated before use."
echo ""
echo "Opening browser for Claude authentication..."
echo ""

# Open Claude auth URL
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "https://claude.ai/login"
elif command -v xdg-open &> /dev/null; then
    xdg-open "https://claude.ai/login"
fi

echo -e "${YELLOW}Please:${NC}"
echo "  1. Log in to your Claude account in the browser"
echo "  2. Return here when authenticated"
echo ""
read -p "Press ENTER when you've logged into Claude..."

# Verify Claude CLI is accessible
echo ""
echo -n "Checking Claude CLI... "
if command -v claude &> /dev/null; then
    echo -e "${GREEN}✓ Available${NC}"
else
    echo -e "${YELLOW}⚠ Claude command not found in PATH${NC}"
    echo "  You may need to restart your terminal after setup"
fi
echo ""

# ============================================================
# PHASE 6: GPT SETUP WIZARD
# ============================================================

clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🚀 OrchestrateOS Setup Wizard${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Now let's set up your Custom GPT. This takes about 2 minutes."
echo ""
read -p "Press ENTER to continue..."

# Extract domain from ngrok URL
if [ "$NGROK_URL" != "NOT_AVAILABLE" ]; then
    NGROK_DOMAIN=$(echo "$NGROK_URL" | sed 's|^https\?://||' | sed 's|/$||')
else
    clear
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}📋 Get Your ngrok Domain${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "We couldn't detect your ngrok domain automatically."
    echo "It should look like this:"
    echo ""
    echo "  upright-constantly-grub.ngrok-free.app"
    echo ""
    read -p "Enter your ngrok domain: " NGROK_DOMAIN

    # Clean up the domain
    NGROK_DOMAIN=$(echo "$NGROK_DOMAIN" | sed 's|^https\?://||' | sed 's|/$||')

    # Validate domain format
    if [[ ! $NGROK_DOMAIN =~ \.ngrok-free\.app$ ]]; then
        echo ""
        echo -e "${YELLOW}⚠️  That doesn't look right. It should end with .ngrok-free.app${NC}"
        echo ""
        read -p "Try again - Enter your ngrok domain: " NGROK_DOMAIN
        NGROK_DOMAIN=$(echo "$NGROK_DOMAIN" | sed 's|^https\?://||' | sed 's|/$||')
    fi

    NGROK_URL="https://$NGROK_DOMAIN"
fi

# Update template files with ngrok URL
INSTRUCTIONS_FILE="$ORCHESTRATE_HOME/instructions_template.json"
YAML_FILE="$ORCHESTRATE_HOME/openapi_template.yaml"

# Create safe domain string for GPT action names (replace dots and hyphens)
SAFE_DOMAIN=$(echo "$NGROK_DOMAIN" | sed 's/[.-]/_/g')

echo ""
echo "Updating configuration with your domain..."

# Update instructions template with safe domain
if [ -f "$INSTRUCTIONS_FILE" ]; then
    sed -i '' "s|\${SAFE_DOMAIN}|$SAFE_DOMAIN|g" "$INSTRUCTIONS_FILE" 2>/dev/null || \
    sed "s|\${SAFE_DOMAIN}|$SAFE_DOMAIN|g" "$INSTRUCTIONS_FILE" > "$INSTRUCTIONS_FILE.tmp" && mv "$INSTRUCTIONS_FILE.tmp" "$INSTRUCTIONS_FILE"
fi

# Update YAML file with ngrok URL
if [ -f "$YAML_FILE" ]; then
    sed -i '' "s|\$DOMAIN|$NGROK_DOMAIN|g" "$YAML_FILE" 2>/dev/null || \
    sed "s|\$DOMAIN|$NGROK_DOMAIN|g" "$YAML_FILE" > "$YAML_FILE.tmp" && mv "$YAML_FILE.tmp" "$YAML_FILE"
fi

echo -e "${GREEN}✓ Configuration updated${NC}"
sleep 1

# Open GPT Editor
clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🌐 Step 1 of 3: Open GPT Editor${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Opening your browser..."
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    open "https://chatgpt.com/gpts/editor"
elif command -v xdg-open &> /dev/null; then
    xdg-open "https://chatgpt.com/gpts/editor"
fi

sleep 2
echo -e "${GREEN}✓ Browser opened${NC}"
echo ""
read -p "Press ENTER when you see the GPT editor..."

# Paste Instructions
clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}📋 Step 2 of 3: Three Copy/Pastes${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "We'll copy things to your clipboard."
echo "You just press Command+V (or Ctrl+V) to paste."
echo ""
echo "Ready? Let's go! 💪"
echo ""
read -p "Press ENTER to continue..."

# Part 1: Instructions
clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}📋 Paste #1: Instructions${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
if [ -f "$INSTRUCTIONS_FILE" ]; then
    cat "$INSTRUCTIONS_FILE" | pbcopy 2>/dev/null || xclip -selection clipboard < "$INSTRUCTIONS_FILE" 2>/dev/null || true
    echo -e "${GREEN}✓ Copied instructions to your clipboard!${NC}"
else
    echo -e "${YELLOW}⚠ Instructions file not found${NC}"
fi
echo ""
echo "Now in your browser:"
echo ""
echo "  1. Click the 'Configure' tab"
echo "  2. Set Model to: GPT-4o (recommended)"
echo "  3. Under Capabilities, UNCHECK 'Web search'"
echo "  4. Find the 'Instructions' box"
echo "  5. Click inside it"
echo "  6. Press Command+V (Mac) or Ctrl+V (Windows)"
echo ""
read -p "Press ENTER after you paste..."

# Part 2: Conversation Starter
clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}💬 Paste #2: Conversation Starter${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Load OrchestrateOS" | pbcopy 2>/dev/null || echo "Load OrchestrateOS" | xclip -selection clipboard 2>/dev/null || true
echo -e "${GREEN}✓ Copied conversation starter to your clipboard!${NC}"
echo ""
echo "Now in your browser:"
echo ""
echo "  1. Scroll down to 'Conversation starters'"
echo "  2. Click the first empty box"
echo "  3. Press Command+V (Mac) or Ctrl+V (Windows)"
echo ""
read -p "Press ENTER after you paste..."

# Part 3: OpenAPI Schema
clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🔌 Paste #3: API Connection${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
if [ -f "$YAML_FILE" ]; then
    cat "$YAML_FILE" | pbcopy 2>/dev/null || xclip -selection clipboard < "$YAML_FILE" 2>/dev/null || true
    echo -e "${GREEN}✓ Copied API schema to your clipboard!${NC}"
else
    echo -e "${YELLOW}⚠ YAML file not found${NC}"
fi
echo ""
echo "Now in your browser:"
echo ""
echo "  1. Scroll down to 'Actions'"
echo "  2. Click 'Create new action'"
echo "  3. You'll see a big text box with some code"
echo "  4. Select ALL that code and delete it"
echo "  5. Press Command+V (Mac) or Ctrl+V (Windows)"
echo "  6. Click the 'Save' button (top right)"
echo ""
read -p "Press ENTER after you paste and save..."

# Test
clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🧪 Step 3 of 3: Test Your Setup${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Almost done! Let's make sure it works."
echo ""
echo "In your browser:"
echo ""
echo "  1. Click 'Preview' (top right corner)"
echo "  2. In the chat that appears, type:"
echo ""
echo "     Load OrchestrateOS"
echo ""
echo "  3. Press ENTER"
echo ""
echo "You should see a table with your tools appear."
echo ""
echo -e "${GREEN}If you see the table → SUCCESS! 🎉${NC}"
echo -e "${YELLOW}If nothing happens → Let us know and we'll help troubleshoot${NC}"
echo ""
read -p "Press ENTER when you've tested it..."

# ============================================================
# PHASE 7: FINAL SUCCESS MESSAGE
# ============================================================

clear
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    SETUP COMPLETE! 🎉                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Your OrchestrateOS is ready to use!${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Endpoints:${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Local Server:  ${BLUE}http://localhost:$FASTAPI_PORT${NC}"
echo -e "  Public URL:    ${BLUE}$NGROK_URL${NC}"
echo -e "  API Endpoint:  ${BLUE}$NGROK_URL/execute_task${NC}"
echo -e "  Health Check:  ${BLUE}$NGROK_URL/supported_actions${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  What You Can Do Now:${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  • Assign tasks from your Custom GPT"
echo "  • Run 'Load OrchestrateOS' anytime to see your tools"
echo "  • Use Claude Code for autonomous task execution"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Logs:${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  FastAPI: /tmp/orchestrate_server.log"
echo "  ngrok:   /tmp/ngrok.log"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  To Stop Services:${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  pkill -f 'uvicorn jarvis:app'"
echo "  pkill -f 'ngrok http'"
echo ""
echo -e "${CYAN}Need help? Just ask in your Custom GPT chat!${NC}"
echo ""
