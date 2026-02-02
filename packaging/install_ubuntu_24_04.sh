#!/bin/bash
set -e

echo "Installing Vocalis..."

INSTALL_DIR="$HOME/.local/share/vocalis"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
SYSTEMD_DIR="$HOME/.config/systemd/user"


# 0. Check Dependencies
REQUIRED_PKGS="python3-venv libportaudio2"

if [ "$XDG_SESSION_TYPE" == "wayland" ]; then
    REQUIRED_PKGS="$REQUIRED_PKGS wl-clipboard wtype"
else
    REQUIRED_PKGS="$REQUIRED_PKGS xdotool xsel"
fi

echo "Checking for missing packages..."
MISSING_PKGS=""
for pkg in $REQUIRED_PKGS; do
    if ! dpkg -l | grep -q " $pkg "; then
        MISSING_PKGS="$MISSING_PKGS $pkg"
    fi
done

if [ -n "$MISSING_PKGS" ]; then
    echo "Missing packages found: $MISSING_PKGS"
    read -p "Install them now with sudo? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ || -z $REPLY ]]; then
        sudo apt update && sudo apt install -y $MISSING_PKGS
    else
        echo "Warning: Vocalis may not work correctly without these packages."
    fi
fi

# 1. Prepare Directory
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    rm -rf "$INSTALL_DIR"
fi
mkdir -p "$INSTALL_DIR"
cp -r ../* "$INSTALL_DIR/"

# 2. Setup Venv
echo "Setting up virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
./venv/bin/pip install -r requirements.txt


# 3. Create Launcher Script
echo "Creating launcher..."
mkdir -p "$BIN_DIR"
cat <<EOF > "$BIN_DIR/vocalis"
#!/bin/bash
export PYTHONPATH="$INSTALL_DIR"
exec "$INSTALL_DIR/venv/bin/python" -m app.main "\$@"
EOF
chmod +x "$BIN_DIR/vocalis"

# 4. Install Desktop File
echo "Installing desktop entry..."
mkdir -p "$DESKTOP_DIR"
# Replace placeholder %HOME%
sed "s|%HOME%|$HOME|g" packaging/desktop/vocalis.desktop > "$DESKTOP_DIR/vocalis.desktop"

# 5. Install Systemd Service
echo "Installing systemd service..."
mkdir -p "$SYSTEMD_DIR"
# Replace placeholder %HOME%
sed "s|%HOME%|$HOME|g" packaging/systemd/vocalis.service > "$SYSTEMD_DIR/vocalis.service"
# Replace XDG_SESSION_TYPE safely
sed -i "s|%XDG_SESSION_TYPE%|$XDG_SESSION_TYPE|g" "$SYSTEMD_DIR/vocalis.service"

systemctl --user daemon-reload
systemctl --user enable vocalis.service
systemctl --user start vocalis.service

echo "------------------------------------------------"
echo "Vocalis installed successfully!"
echo "------------------------------------------------"
echo "1. Run 'vocalis --gui' to start the tray."
echo "2. Setup your Wayland hotkey (see docs/wayland.md)."
echo "   Command: vocalis --listen"
echo "------------------------------------------------"
