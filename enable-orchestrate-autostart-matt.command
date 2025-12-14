#!/bin/bash
# OrchestrateOS Auto-Start Enabler for Matt
# Double-click this file to permanently enable auto-start on boot

set -e

PLIST_PATH="$HOME/Library/LaunchAgents/com.orchestrateos.services.plist"
WORKING_DIR="$HOME/Orchestrate Github/orchestrate-jarvis"

echo "🚀 Installing OrchestrateOS Auto-Start..."
echo ""

# Kill any existing processes on port 5001
echo "🔪 Killing existing processes..."
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
pkill -f ngrok 2>/dev/null || true
sleep 2

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"

# Create the LaunchAgent plist
cat > "$PLIST_PATH" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.orchestrateos.services</string>
    <key>WorkingDirectory</key>
    <string>WORKING_DIR_PLACEHOLDER</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd WORKING_DIR_PLACEHOLDER && source VENV_PATH_PLACEHOLDER/bin/activate && uvicorn jarvis:app --host 0.0.0.0 --port 5001 > /tmp/orchestrate-uvicorn.log 2>&1 &amp; sleep 3 &amp;&amp; ngrok http --domain=deeply-crisp-grizzly.ngrok-free.app 5001 > /tmp/orchestrate-ngrok.log 2>&1</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/orchestrate-services.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/orchestrate-services-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF

# Detect actual working directory
if [ -d "$HOME/Orchestrate Github/orchestrate-jarvis" ]; then
    ACTUAL_WORKING_DIR="$HOME/Orchestrate Github/orchestrate-jarvis"
elif [ -d "$HOME/orchestrate-jarvis" ]; then
    ACTUAL_WORKING_DIR="$HOME/orchestrate-jarvis"
else
    echo "❌ Could not find orchestrate-jarvis directory"
    echo "Please update WORKING_DIR in the script"
    exit 1
fi

# Detect venv location
if [ -d "$HOME/venv" ]; then
    VENV_PATH="$HOME/venv"
elif [ -d "$ACTUAL_WORKING_DIR/venv" ]; then
    VENV_PATH="$ACTUAL_WORKING_DIR/venv"
else
    echo "❌ Could not find venv directory"
    echo "Please update VENV_PATH in the script"
    exit 1
fi

# Replace placeholders
sed -i '' "s|WORKING_DIR_PLACEHOLDER|$ACTUAL_WORKING_DIR|g" "$PLIST_PATH"
sed -i '' "s|VENV_PATH_PLACEHOLDER|$VENV_PATH|g" "$PLIST_PATH"

echo "✅ Created LaunchAgent plist at: $PLIST_PATH"
echo "   Working Directory: $ACTUAL_WORKING_DIR"
echo "   Virtual Environment: $VENV_PATH"

# Unload if already loaded (ignore errors)
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load the LaunchAgent
launchctl load "$PLIST_PATH"

echo "✅ LaunchAgent loaded and activated"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 OrchestrateOS Auto-Start ENABLED!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Services will now start automatically on login"
echo "Your OrchestrateOS URL: https://deeply-crisp-grizzly.ngrok-free.app"
echo ""
echo "To disable auto-start, run:"
echo "  launchctl unload ~/Library/LaunchAgents/com.orchestrateos.services.plist"
echo ""

# Keep window open briefly so user can see success message
sleep 5
