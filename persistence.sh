#!/bin/bash

# ----------------------------------------------------------------------
# Automated systemd persistence setup script
# Usage: sudo ./setup_persistence.sh -n SERVICE_NAME -b BINARY_PATH [-d DESCRIPTION] [-a AFTER_TARGET]
# ----------------------------------------------------------------------

set -e  # Exit on any error

# Default values
AFTER_TARGET="network.target"
DESCRIPTION="System maintenance helper"

# Function to display usage
usage() {
    echo "Usage: $0 -n SERVICE_NAME -b BINARY_PATH [-d DESCRIPTION] [-a AFTER_TARGET]"
    echo "  -n    Service name (e.g., systemd-network-helper, cron-update)"
    echo "  -b    Absolute path to your binary"
    echo "  -d    Description (default: 'System maintenance helper')"
    echo "  -a    systemd target to start after (default: network.target)"
    echo "Example: $0 -n systemd-network-helper -b /usr/local/bin/mybinary -d 'Network config helper'"
    exit 1
}

# Parse command line arguments
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

# Validate required arguments
if [ -z "$SERVICE_NAME" ] || [ -z "$BINARY_PATH" ]; then
    echo "Error: Service name (-n) and binary path (-b) are required."
    usage
fi

# Ensure binary path is absolute and exists
if [[ "$BINARY_PATH" != /* ]]; then
    echo "Error: Binary path must be absolute (start with /)."
    exit 1
fi

if [ ! -f "$BINARY_PATH" ]; then
    echo "Error: Binary not found at $BINARY_PATH"
    exit 1
fi

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)."
    exit 1
fi

# Construct service file path
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Check if service file already exists
if [ -f "$SERVICE_FILE" ]; then
    echo "Warning: $SERVICE_FILE already exists."
    read -p "Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborting."
        exit 1
    fi
fi

# Create the systemd service unit file
echo "Creating systemd service file: $SERVICE_FILE"
cat > "$SERVICE_FILE" <<EOF
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
EOF

# Set proper permissions
chmod 644 "$SERVICE_FILE"

# Reload systemd, enable and start the service
echo "Reloading systemd daemon..."
systemctl daemon-reload

echo "Enabling $SERVICE_NAME to start on boot..."
systemctl enable "$SERVICE_NAME.service"

echo "Starting $SERVICE_NAME now..."
systemctl start "$SERVICE_NAME.service"

# Show status
echo -e "\nService status:"
systemctl status "$SERVICE_NAME.service" --no-pager

echo -e "\n✅ Persistence setup complete. Service '$SERVICE_NAME' will run at every boot and auto-restart on failure."
echo "To stop: systemctl stop $SERVICE_NAME"
echo "To disable: systemctl disable $SERVICE_NAME"