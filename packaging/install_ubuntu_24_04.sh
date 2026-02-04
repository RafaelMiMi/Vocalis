#!/bin/bash
set -e

echo "Installing Vocalis..."

INSTALL_DIR="$HOME/.local/share/vocalis"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
SYSTEMD_DIR="$HOME/.config/systemd/user"


# Determine exact python dev package needed (e.g. python3.12-dev)
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_DEV_PKG="python3-dev"
if [ ! -z "$PY_VERSION" ]; then
    PY_DEV_PKG="python3-dev python${PY_VERSION}-dev libpython${PY_VERSION}-dev"
fi

REQUIRED_PKGS="python3-venv build-essential libportaudio2 pkg-config $PY_DEV_PKG libpython3-all-dev"

if [ "$XDG_SESSION_TYPE" == "wayland" ]; then
    REQUIRED_PKGS="$REQUIRED_PKGS wl-clipboard wtype"
else
    REQUIRED_PKGS="$REQUIRED_PKGS xdotool xsel"
fi

echo "Checking for missing packages..."
MISSING_PKGS=""
for pkg in $REQUIRED_PKGS; do
    if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
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
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "DEBUG: Script location: $SCRIPT_DIR"
echo "DEBUG: Project root: $PROJECT_ROOT"
echo "Installing from $PROJECT_ROOT to $INSTALL_DIR..."

if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo "ERROR: requirements.txt not found in project root ($PROJECT_ROOT)"
    # Fallback: try to find it in current dir or parent
    if [ -f "./requirements.txt" ]; then
        PROJECT_ROOT="$(pwd)"
        echo "Found in current dir, updating root to: $PROJECT_ROOT"
    elif [ -f "../requirements.txt" ]; then
        PROJECT_ROOT="$(dirname "$(pwd)")"
        echo "Found in parent dir, updating root to: $PROJECT_ROOT"
    else
        echo "CRITICAL: Could not locate requirements.txt anywhere."
        exit 1
    fi
fi

if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    rm -rf "$INSTALL_DIR"
fi
mkdir -p "$INSTALL_DIR"

# Copy everything including hidden files
echo "Copying files..."
cp -a "$PROJECT_ROOT/." "$INSTALL_DIR/"

# 2. Setup Venv
echo "Setting up virtual environment..."
echo "DEBUG SCRIPT VERSION: 2026-02-04-v3 (Run git pull if you don't see this!)"
cd "$INSTALL_DIR"
echo "DEBUG: CWD is now $(pwd)"

if [ ! -f "requirements.txt" ]; then
    echo "ERROR: Copy failed? requirements.txt missing in target."
    ls -la
    exit 1
fi

# Verify Python headers exist and setup environment securely
echo "Probing for Python headers directly..."
if command -v python3-config &> /dev/null; then
    PY_CFLAGS=$(python3-config --cflags)
    echo "python3-config says: $PY_CFLAGS"
    export CFLAGS="$CFLAGS $PY_CFLAGS"
else
    echo "python3-config not found. Falling back to manual search."
fi

# Manual fallback search
PYTHON_HEADER_PATH=$(find /usr/include -name "Python.h" 2>/dev/null | head -n 1)
if [ -z "$PYTHON_HEADER_PATH" ]; then
    echo "CRITICAL WARNING: Python.h not found in /usr/include range."
    # Check multiarch
    PYTHON_HEADER_PATH=$(find /usr/lib -name "Python.h" 2>/dev/null | head -n 1)
fi

if [ -n "$PYTHON_HEADER_PATH" ]; then
    echo "Found Python.h at: $PYTHON_HEADER_PATH"
    PYTHON_INCLUDE_DIR=$(dirname "$PYTHON_HEADER_PATH")
    export C_INCLUDE_PATH="$PYTHON_INCLUDE_DIR:$C_INCLUDE_PATH"
    export CPLUS_INCLUDE_PATH="$PYTHON_INCLUDE_DIR:$CPLUS_INCLUDE_PATH"
    
    # Also handle multiarch config.c includes if needed
    export CFLAGS="$CFLAGS -I$PYTHON_INCLUDE_DIR"
    echo "Manually exported include path: $PYTHON_INCLUDE_DIR"
else
    echo "CRITICAL ERROR: Python.h could not be found anywhere. Build WILL fail." 
fi

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install setuptools wheel
# Try to install evdev explicitly first
echo "Installing evdev..."
./venv/bin/pip install evdev || echo "Warning: evdev install failed, will retry with requirements."

./venv/bin/pip install "faster-whisper"
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

# Check for input group permissions (crucial for evdev/hotkeys)
if ! groups | grep -q "\binput\b"; then
    echo "WARNING: Your user is NOT in the 'input' group."
    echo "This is required for detecting global hotkeys (evdev)."
    read -p "Add user '$USER' to 'input' group now? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ || -z $REPLY ]]; then
        sudo usermod -aG input "$USER"
        echo "MARKED FOR RESTART: You must LOG OUT and LOG BACK IN for this to take effect!"
    else
        echo "Warning: Hotkeys may not work until you fix permissions."
    fi
fi

echo "1. Run 'vocalis --gui' to start the tray."
echo "2. If you are on Wayland, you MUST set a custom system shortcut."
echo "   Command: vocalis --listen"
echo "------------------------------------------------"
