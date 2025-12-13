#!/bin/bash
#
# OrchestrateOS Remote Install Script
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/unmistakablecreative/orchestrate-remote-install/main/install_orchestrate.sh | bash -s -- --ngrok-token YOUR_TOKEN --ngrok-domain YOUR_DOMAIN

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ORCHESTRATE_HOME="$HOME/Orchestrate Github/orchestrate-jarvis"
GITHUB_REPO="https://github.com/unmistakablecreative/orchestrate-remote-install.git"
NGROK_TOKEN=""
NGROK_DOMAIN=""
FASTAPI_PORT=5001

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

echo -e "${YELLOW}[1/8] Installing Claude Code CLI...${NC}"
curl -fsSL https://claude.ai/install.sh | bash

if [ -f "$HOME/.zshrc" ]; then
    source "$HOME/.zshrc" 2>/dev/null || true
elif [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc" 2>/dev/null || true
fi

echo -e "${YELLOW}[2/8] Setting up ngrok...${NC}"
if ! command -v ngrok &> /dev/null; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install ngrok/ngrok/ngrok
        else
            curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-amd64.zip -o ngrok.zip
            unzip -o ngrok.zip
            sudo mv ngrok /usr/local/bin/
            rm ngrok.zip
        fi
    else
        curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz | tar xz
        sudo mv ngrok /usr/local/bin/
    fi
fi

if [ -n "$NGROK_TOKEN" ]; then
    ngrok config add-authtoken "$NGROK_TOKEN"
fi

echo -e "${YELLOW}[3/8] Cloning OrchestrateOS repository...${NC}"
if [ -d "$ORCHESTRATE_HOME" ]; then
    cd "$ORCHESTRATE_HOME"
    git pull origin main || true
else
    mkdir -p "$(dirname "$ORCHESTRATE_HOME")"
    git clone "$GITHUB_REPO" "$ORCHESTRATE_HOME"
fi
cd "$ORCHESTRATE_HOME"

if [ -n "$NGROK_DOMAIN" ]; then
    echo "Configuring template files with domain: $NGROK_DOMAIN"
    SAFE_DOMAIN=$(echo "$NGROK_DOMAIN" | sed 's/[.-]/_/g')

    if [ -f "$ORCHESTRATE_HOME/openapi_template.yaml" ]; then
        sed -i '' "s|\\\$DOMAIN|$NGROK_DOMAIN|g" "$ORCHESTRATE_HOME/openapi_template.yaml" 2>/dev/null || \
        sed "s|\\\$DOMAIN|$NGROK_DOMAIN|g" "$ORCHESTRATE_HOME/openapi_template.yaml" > "$ORCHESTRATE_HOME/openapi_template.yaml.tmp" && \
        mv "$ORCHESTRATE_HOME/openapi_template.yaml.tmp" "$ORCHESTRATE_HOME/openapi_template.yaml"
        echo -e "  ${GREEN}✓${NC} Updated openapi_template.yaml"
    fi

    if [ -f "$ORCHESTRATE_HOME/instructions_template.json" ]; then
        sed -i '' "s|\${SAFE_DOMAIN}|$SAFE_DOMAIN|g" "$ORCHESTRATE_HOME/instructions_template.json" 2>/dev/null || \
        sed "s|\${SAFE_DOMAIN}|$SAFE_DOMAIN|g" "$ORCHESTRATE_HOME/instructions_template.json" > "$ORCHESTRATE_HOME/instructions_template.json.tmp" && \
        mv "$ORCHESTRATE_HOME/instructions_template.json.tmp" "$ORCHESTRATE_HOME/instructions_template.json"
        echo -e "  ${GREEN}✓${NC} Updated instructions_template.json"
    fi
fi

echo -e "${YELLOW}[4/8] Installing Python dependencies...${NC}"
pip3 install -r requirements.txt --quiet

echo -e "${YELLOW}[5/8] Resetting data files for clean install...${NC}"
mkdir -p "$ORCHESTRATE_HOME/data"
echo "[]" > "$ORCHESTRATE_HOME/data/claude_task_queue.json"
echo "{}" > "$ORCHESTRATE_HOME/data/claude_task_results.json"
echo "{}" > "$ORCHESTRATE_HOME/data/outline_queue.json"

echo -e "${YELLOW}[6/8] Starting FastAPI server...${NC}"
pkill -f "uvicorn jarvis:app" 2>/dev/null || true
nohup python3 -m uvicorn jarvis:app --host 0.0.0.0 --port $FASTAPI_PORT > /tmp/orchestrate_server.log 2>&1 &
sleep 3

echo -e "${YELLOW}[7/8] Starting ngrok tunnel...${NC}"
pkill -f "ngrok http" 2>/dev/null || true
if [ -n "$NGROK_DOMAIN" ]; then
    nohup ngrok http $FASTAPI_PORT --domain="$NGROK_DOMAIN" > /tmp/ngrok.log 2>&1 &
else
    nohup ngrok http $FASTAPI_PORT > /tmp/ngrok.log 2>&1 &
fi
sleep 5

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; tunnels=json.load(sys.stdin).get('tunnels',[]); print(tunnels[0]['public_url'] if tunnels else 'NOT_AVAILABLE')" 2>/dev/null || echo "NOT_AVAILABLE")

echo -e "${YELLOW}[8/8] Running verification checks...${NC}"
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                  SERVICE STATUS CHECK                       ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -n "  FastAPI Server (localhost:$FASTAPI_PORT)... "
if curl -s "http://localhost:$FASTAPI_PORT/" 2>/dev/null | grep -q "online"; then
    echo -e "${GREEN}✓ RUNNING${NC}"
else
    echo -e "${RED}✗ NOT RESPONDING${NC}"
fi

echo -n "  ngrok Tunnel... "
if [ "$NGROK_URL" != "NOT_AVAILABLE" ]; then
    echo -e "${GREEN}✓ ACTIVE${NC}"
else
    echo -e "${RED}✗ NOT AVAILABLE${NC}"
fi

echo ""
echo -e "${GREEN}  Server URL:${NC} http://localhost:$FASTAPI_PORT"
echo -e "${GREEN}  Public URL:${NC} $NGROK_URL"
echo ""

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  INSTALLATION COMPLETE!                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
