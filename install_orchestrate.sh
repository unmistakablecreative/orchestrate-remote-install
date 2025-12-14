#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ORCHESTRATE_HOME="$HOME/Orchestrate Github/orchestrate-jarvis"
GITHUB_REPO="https://github.com/unmistakablecreative/orchestrate-remote-install.git"
NGROK_TOKEN=""
NGROK_DOMAIN=""
FASTAPI_PORT=5001

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --ngrok-token) NGROK_TOKEN="$2"; shift 2 ;;
        --ngrok-domain) NGROK_DOMAIN="$2"; shift 2 ;;
        --port) FASTAPI_PORT="$2"; shift 2 ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         OrchestrateOS Remote Install Script                 ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}[1/10] Checking Xcode Command Line Tools...${NC}"
if ! xcode-select -p &>/dev/null; then
    echo "Installing Xcode Command Line Tools..."
    xcode-select --install
    echo "Please complete the Xcode installation popup, then run this script again."
    exit 1
fi

echo -e "${GREEN}[2/10] Checking Homebrew...${NC}"
if ! command -v brew &>/dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
fi

echo -e "${GREEN}[3/10] Checking Python3...${NC}"
if ! command -v python3 &>/dev/null; then
    echo "Installing Python3..."
    brew install python3
fi

echo -e "${GREEN}[4/10] Checking pip3...${NC}"
if ! command -v pip3 &>/dev/null; then
    echo "Installing pip3..."
    python3 -m ensurepip --upgrade
fi

echo -e "${GREEN}[5/10] Installing Claude Code CLI...${NC}"
curl -fsSL https://claude.ai/install.sh | bash
source ~/.zshrc 2>/dev/null || true

echo -e "${GREEN}[6/10] Installing ngrok...${NC}"
if ! command -v ngrok &>/dev/null; then
    brew install ngrok/ngrok/ngrok
fi
if [ -n "$NGROK_TOKEN" ]; then
    ngrok config add-authtoken "$NGROK_TOKEN"
fi

echo -e "${GREEN}[7/10] Cloning repository...${NC}"
if [ -d "$ORCHESTRATE_HOME" ]; then
    cd "$ORCHESTRATE_HOME" && git pull origin main || true
else
    mkdir -p "$(dirname "$ORCHESTRATE_HOME")"
    git clone "$GITHUB_REPO" "$ORCHESTRATE_HOME"
fi
cd "$ORCHESTRATE_HOME"

echo -e "${GREEN}[8/10] Installing Python dependencies...${NC}"
pip3 install -r requirements.txt

echo -e "${GREEN}[9/10] Starting FastAPI server...${NC}"
mkdir -p "$ORCHESTRATE_HOME/data"
echo "[]" > "$ORCHESTRATE_HOME/data/claude_task_queue.json"
echo "{}" > "$ORCHESTRATE_HOME/data/claude_task_results.json"
pkill -f "uvicorn jarvis:app" 2>/dev/null || true
nohup python3 -m uvicorn jarvis:app --host 0.0.0.0 --port $FASTAPI_PORT > /tmp/orchestrate_server.log 2>&1 &
sleep 3

echo -e "${GREEN}[10/10] Starting ngrok tunnel...${NC}"
pkill -f "ngrok http" 2>/dev/null || true
if [ -n "$NGROK_DOMAIN" ]; then
    nohup ngrok http $FASTAPI_PORT --domain="$NGROK_DOMAIN" > /tmp/ngrok.log 2>&1 &
else
    nohup ngrok http $FASTAPI_PORT > /tmp/ngrok.log 2>&1 &
fi
sleep 3

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo "Server: http://localhost:$FASTAPI_PORT"
echo "Public: https://$NGROK_DOMAIN"
curl -s "http://localhost:$FASTAPI_PORT/" || echo -e "${RED}Server not responding${NC}"
