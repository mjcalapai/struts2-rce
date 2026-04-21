set -e
 
AFTER_TARGET="network.target"
DESCRIPTION="System maintenance helper"
 
usage() {
    echo "Usage: $0 -n SERVICE_NAME -b BINARY_PATH [-d DESCRIPTION] [-a AFTER_TARGET]"
    echo "  -n    Service name (e.g., systemd-network-helper)"
    echo "  -b    Absolute path to your binary"
    echo "  -d    Description (default: 'System maintenance helper')"
    echo "  -a    systemd target to start after (default: network.target)"
    exit 1
}
 
while getopts "n:b:d:a:h" opt; do
    case "$opt" in
        n) SERVICE_NAME="$OPTARG" ;;
        b) BINARY_PATH="$OPTARG" ;;
        d) DESCRIPTION="$OPTARG" ;;
        a) AFTER_TARGET="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done
 
if [ -z "$SERVICE_NAME" ] || [ -z "$BINARY_PATH" ]; then
    echo "[-] Service name (-n) and binary path (-b) are required."
    usage
fi
 
if [[ "$BINARY_PATH" != /* ]]; then
    echo "[-] Binary path must be absolute (start with /)."
    exit 1
fi
 
if [ ! -f "$BINARY_PATH" ]; then
    echo "[-] Binary not found at $BINARY_PATH"
    exit 1
fi
 
if [ "$EUID" -ne 0 ]; then
    echo "[-] Please run as root (use sudo)."
    exit 1
fi
 
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
 
if [ -f "$SERVICE_FILE" ]; then
    echo "[!] $SERVICE_FILE already exists, overwriting..."
fi
 
echo "[*] Creating $SERVICE_FILE"
cat > "$SERVICE_FILE" <<UNIT
[Unit]
Description=$DESCRIPTION
After=$AFTER_TARGET
 
[Service]
Type=simple
ExecStart=$BINARY_PATH
Restart=on-failure
RestartSec=5
 
[Install]
WantedBy=multi-user.target
UNIT
 
chmod 644 "$SERVICE_FILE"
 
echo "[*] Reloading systemd daemon..."
systemctl daemon-reload
 
echo "[*] Enabling $SERVICE_NAME..."
systemctl enable "${SERVICE_NAME}.service"
 
echo "[*] Starting $SERVICE_NAME..."
systemctl start "${SERVICE_NAME}.service"
 
echo "[+] Persistence set. '$SERVICE_NAME' will run at every boot and restart on failure."