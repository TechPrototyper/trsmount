#!/bin/bash
# Wrapper for trs80_fuse.py
# Usage: trsmount <disk_image> <mount_point>

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_EXEC="python3"

# Check if venv exists and use it
if [ -d "$DIR/.venv" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python3"
fi

"$PYTHON_EXEC" "$DIR/trs80_fuse.py" "$@"
