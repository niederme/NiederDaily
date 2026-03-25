#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_DIR/.venv"
SCRIPT_PATH="$REPO_DIR/niederdaily.py"
CONFIG_DIR="$HOME/.niederdaily"
LOG_DIR="$CONFIG_DIR/logs"
PLIST_NAME="me.nieder.daily.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "NiederDaily Installer"
echo "====================="

# 1. Create config directory
mkdir -p "$CONFIG_DIR" "$LOG_DIR"
echo "✓ Created $CONFIG_DIR"

# 2. Write config template if not present
CONFIG_PATH="$CONFIG_DIR/config.json"
if [ ! -f "$CONFIG_PATH" ]; then
cat > "$CONFIG_PATH" <<'EOF'
{
  "recipient_email": "FILL_IN",
  "default_location": { "name": "Warwick, NY", "lat": 41.2512, "lon": -74.3607 },
  "nyt_api_key": "FILL_IN",
  "anthropic_api_key": "FILL_IN",
  "reminders_lists": []
}
EOF
  echo "✓ Created config template at $CONFIG_PATH"
  echo "  → Edit this file and fill in your API keys before continuing."
else
  echo "- Config already exists at $CONFIG_PATH (skipped)"
fi

# 3. Create venv and install dependencies
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
echo "✓ Virtual environment ready at $VENV_DIR"

PYTHON_PATH="$VENV_DIR/bin/python"

# 4. Generate plist
sed \
  -e "s|__PYTHON_PATH__|$PYTHON_PATH|g" \
  -e "s|__SCRIPT_PATH__|$SCRIPT_PATH|g" \
  -e "s|__LOG_DIR__|$LOG_DIR|g" \
  "$REPO_DIR/setup/me.nieder.daily.plist.template" > "$PLIST_DEST"
echo "✓ LaunchAgent plist written to $PLIST_DEST"

echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_PATH — fill in recipient_email, nyt_api_key, anthropic_api_key"
echo "  2. Download client_secret.json from Google Cloud Console → $CONFIG_DIR/client_secret.json"
echo "  3. Run preflight:  $PYTHON_PATH $SCRIPT_PATH --preflight"
echo "  4. Load agent:     launchctl load $PLIST_DEST"
