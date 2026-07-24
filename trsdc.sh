#!/bin/bash
# Wrapper for trsdc.py
# Usage: trsdc -i <input_file> -o <output_file> [-if <spec>] [-of <spec>] [-v]

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_EXEC="python3"

if [ -d "$DIR/.venv" ]; then
    PYTHON_EXEC="$DIR/.venv/bin/python3"
fi

"$PYTHON_EXEC" "$DIR/trsdc.py" "$@"
