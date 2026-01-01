#!/bin/bash
# Setup script for trsmount

INSTALL_DIR="/usr/local/share/trsmount"
BIN_DIR="/usr/local/bin"

echo "Installing trsmount..."

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 could not be found."
    exit 1
fi

# 2. Ask user for installation type
echo "This script can install trsmount system-wide (requires sudo)."
read -p "Do you want to proceed with system-wide installation? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setting up local development environment only..."
    python3 -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
    chmod +x trsmount.sh
    echo "Done. Use ./trsmount.sh to run."
    exit 0
fi

# 3. System-wide installation
echo "Creating installation directory at $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo cp trs80_driver.py trs80_fuse.py superzap.py catasm.py requirements.txt "$INSTALL_DIR/"

echo "Setting up virtual environment in $INSTALL_DIR..."
sudo python3 -m venv "$INSTALL_DIR/.venv"
sudo "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

echo "Creating executables in $BIN_DIR..."

# trsmount
sudo tee "$BIN_DIR/trsmount" > /dev/null <<EOF
#!/bin/bash
export TRS_PROG_NAME="trsmount"
"$INSTALL_DIR/.venv/bin/python3" "$INSTALL_DIR/trs80_fuse.py" "\$@"
EOF
sudo chmod +x "$BIN_DIR/trsmount"

# superzap
sudo tee "$BIN_DIR/superzap" > /dev/null <<EOF
#!/bin/bash
export TRS_PROG_NAME="superzap"
"$INSTALL_DIR/.venv/bin/python3" "$INSTALL_DIR/superzap.py" "\$@"
EOF
sudo chmod +x "$BIN_DIR/superzap"

# catasm
sudo tee "$BIN_DIR/catasm" > /dev/null <<EOF
#!/bin/bash
export TRS_PROG_NAME="catasm"
"$INSTALL_DIR/.venv/bin/python3" "$INSTALL_DIR/catasm.py" "\$@"
EOF
sudo chmod +x "$BIN_DIR/catasm"

echo "Installation complete!"
echo "You can now use 'trsmount', 'superzap', and 'catasm' from anywhere."
