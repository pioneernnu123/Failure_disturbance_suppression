#!/bin/sh
# //LZU CHANGE
set -eu

# //LZU CHANGE
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

# //LZU CHANGE
run_as_root()
{
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        echo "This script must be run as root or with sudo installed." >&2
        exit 1
    fi
}

# //LZU CHANGE
make

# //LZU CHANGE
if grep -q '^phys_mem ' /proc/modules; then
    run_as_root rmmod phys_mem
fi

# //LZU CHANGE
run_as_root insmod ./phys_mem.ko
run_as_root chmod 777 /dev/phys_mem
run_as_root chmod 444 /proc/kpage*

echo OK
