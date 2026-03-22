#!/bin/bash
set -e

echo "=== Installing LocalWhisper ==="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Install Ollama if not present
if ! command -v ollama &> /dev/null; then
    echo "Installing Ollama..."
    brew install ollama
fi

# Start Ollama service
echo "Starting Ollama..."
ollama serve &>/dev/null &
sleep 2

# Pull the LLM model
echo "Pulling Qwen2.5:3b model..."
ollama pull qwen2.5:3b

# Set up Python environment
echo "Setting up Python environment..."
cd "$PROJECT_DIR"
uv sync

# Create config if not exists
CONFIG_DIR="$HOME/.config/localwhisper"
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    mkdir -p "$CONFIG_DIR"
    cp "$PROJECT_DIR/config.example.yaml" "$CONFIG_DIR/config.yaml"
    echo "Created config at $CONFIG_DIR/config.yaml"
fi

# Create data directory
mkdir -p "$HOME/.local/share/localwhisper"

# Install launchd service
PLIST_NAME="com.localwhisper.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/.venv/bin/python</string>
        <string>-m</string>
        <string>localwhisper.app</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/.local/share/localwhisper/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.local/share/localwhisper/stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "Installed launchd service at $PLIST_PATH"

echo ""
echo "=== Installation complete ==="
echo ""
echo "IMPORTANT: Grant Accessibility permission to Terminal/iTerm"
echo "  System Settings > Privacy & Security > Accessibility"
echo ""
echo "To start now:  launchctl load $PLIST_PATH"
echo "To stop:       launchctl unload $PLIST_PATH"
echo "To run manually: cd $PROJECT_DIR && uv run localwhisper"
