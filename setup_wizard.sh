#!/bin/bash
#
# OrchestrateOS Setup Wizard (Part 2: Authentication & GPT Setup)
# Run after install_orchestrate.sh completes
#
# This script handles:
# - Phase 5: Claude Code authentication
# - Phase 6: GPT setup wizard (simplified - files already configured)
# - Phase 7: Final success message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory (where template files are)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTRUCTIONS_FILE="$SCRIPT_DIR/instructions_template.json"
YAML_FILE="$SCRIPT_DIR/openapi_template.yaml"

# Load config from install script for display purposes
ORCHESTRATE_HOME="$HOME/Orchestrate Github/orchestrate-jarvis"
FASTAPI_PORT=5001
NGROK_URL="NOT_AVAILABLE"

CONFIG_FILE="$ORCHESTRATE_HOME/.install_config"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Verify template files exist
if [ ! -f "$INSTRUCTIONS_FILE" ]; then
    echo -e "${RED}ERROR: instructions_template.json not found at $INSTRUCTIONS_FILE${NC}"
    echo "The install script may have failed. Please run install_orchestrate.sh first."
    exit 1
fi

if [ ! -f "$YAML_FILE" ]; then
    echo -e "${RED}ERROR: openapi_template.yaml not found at $YAML_FILE${NC}"
    echo "The install script may have failed. Please run install_orchestrate.sh first."
    exit 1
fi

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
# PHASE 6: GPT SETUP WIZARD (SIMPLIFIED)
# ============================================================

clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🚀 OrchestrateOS Setup Wizard${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Now let's set up your Custom GPT. This takes about 2 minutes."
echo ""
echo -e "${GREEN}✓ Your configuration files are already set up!${NC}"
echo ""
read -p "Press ENTER to start..."

# Step 1: Open GPT Editor
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

# Step 2: Three Copy/Pastes
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

# Paste #1: Instructions
clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}📋 Paste #1: Instructions${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
cat "$INSTRUCTIONS_FILE" | pbcopy 2>/dev/null || xclip -selection clipboard < "$INSTRUCTIONS_FILE" 2>/dev/null || true
echo -e "${GREEN}✓ Copied instructions to your clipboard!${NC}"
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

# Paste #2: Conversation Starter
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

# Paste #3: OpenAPI Schema
clear
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}🔌 Paste #3: API Connection${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
cat "$YAML_FILE" | pbcopy 2>/dev/null || xclip -selection clipboard < "$YAML_FILE" 2>/dev/null || true
echo -e "${GREEN}✓ Copied API schema to your clipboard!${NC}"
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

# Step 3: Test
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
