#!/bin/bash
set -e

echo "Installing Vocalis for macOS..."

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "Error: Homebrew is not installed. Please install Homebrew first: https://brew.sh/"
    exit 1
fi

echo "Installing system dependencies (ffmpeg, pkg-config)..."
brew install ffmpeg pkg-config

INSTALL_DIR="$HOME/.local/share/vocalis"
BIN_DIR="$HOME/.local/bin"

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
./venv/bin/pip install --upgrade pip
./venv/bin/pip install "Cython<3.0" setuptools wheel

# Install PyAV with NO build isolation to ensure it uses our Cython 0.29
# AND install faster-whisper manually to ensure it doesn't trigger a re-build of av
./venv/bin/pip install --no-build-isolation "av>=12.0.0"
./venv/bin/pip install "faster-whisper" --no-deps

# Install remaining requirements
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

# Add to PATH if likely missing
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "Warning: $HOME/.local/bin is not in your PATH."
    echo "Add the following to your ~/.zshrc or ~/.bash_profile:"
    echo 'export PATH="$HOME/.local/bin:$PATH"'
fi

echo "------------------------------------------------"
echo "Vocalis installed successfully!"
echo "------------------------------------------------"
echo "1. Run 'vocalis --gui' to start."
echo "2. Grant 'Accessibility' permissions when prompted (for paste automation)."
echo "3. Grant 'System Events' permissions if prompted (for window detection)."
echo "------------------------------------------------"
