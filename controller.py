#!/usr/bin/env python3
"""
operator.py — Operator CLI for the C2 Listening Post
------------------------------------------------------
Talks to listening_post.py (Flask-RESTful + Supabase) over plain HTTP/JSON.

Commands
  list-tasks     GET  /tasks
  list-results   GET  /results
  list-history   GET  /history
  add-task       POST /tasks   (requires --title and --tasktype; extra --params
                                key=value pairs are forwarded as task parameters)

Usage
  python operator.py [--server URL] [--timeout N]

  python operator.py add-task --title "Run whoami" --tasktype execute --params command=whoami
  python operator.py add-task --title "Configure beacon" --tasktype configure --params dwell=10,running=true
  python operator.py list-tasks
  python operator.py list-results
  python operator.py list-history
"""

import sys
import json
import argparse

import requests
from requests.exceptions import ConnectionError, Timeout, HTTPError

# ── optional pretty-printing ──────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.table import Table
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False

# ── optional REPL enhancements ────────────────────────────────────────────────
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import WordCompleter
    _PT = True
except ImportError:
    _PT = False


DEFAULT_SERVER = "http://127.0.0.1:5000"

# ─────────────────────────────────────────────────────────────────────────────
#  Output helpers
# ─────────────────────────────────────────────────────────────────────────────

def ok(msg):
    if _RICH: console.print(f"[bold green][+][/bold green] {msg}")
    else: print(f"[+] {msg}")

def info(msg):
    if _RICH: console.print(f"[bold cyan][*][/bold cyan] {msg}")
    else: print(f"[*] {msg}")

def warn(msg):
    if _RICH: console.print(f"[bold yellow][!][/bold yellow] {msg}")
    else: print(f"[!] {msg}")

def err(msg):
    if _RICH: console.print(f"[bold red][-][/bold red] {msg}", highlight=False)
    else: print(f"[-] {msg}", file=sys.stderr)

def pretty(data, title=""):
    text = json.dumps(data, indent=2)
    if _RICH:
        console.print(Panel(
            Syntax(text, "json", theme="monokai", word_wrap=True),
            title=f"[bold]{title}[/bold]" if title else "",
            border_style="cyan",
        ))
    else:
        if title:
            print(f"\n── {title} ──")
        print(text)

BANNER = r"""
  ██████╗██████╗      ██████╗██╗     ██╗
 ██╔════╝╚════██╗    ██╔════╝██║     ██║
 ██║      █████╔╝    ██║     ██║     ██║
 ██║     ██╔═══╝     ██║     ██║     ██║
 ╚██████╗███████╗    ╚██████╗███████╗██║
  ╚═════╝╚══════╝     ╚═════╝╚══════╝╚═╝
   Operator CLI  ·  Listening Post Edition
"""

HELP_TEXT = """
  list-tasks                              List all tasks in the DB
  list-results                            List all results returned by the implant
  list-history                            List the full task + result history
  add-task --title T --tasktype TYPE      Queue a new task
           [--desc D]                       Optional description
           [--params key=val,key=val]        Extra task parameters (e.g. command=whoami)
  help                                    Show this message
  exit / quit                             Exit the CLI
"""

# ─────────────────────────────────────────────────────────────────────────────
#  HTTP helpers
# ─────────────────────────────────────────────────────────────────────────────

class LPClient:
    """Thin wrapper around requests for the listening post REST API."""

    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self._s       = requests.Session()
        self._s.headers.update({"Content-Type": "application/json"})

    # ── low-level ─────────────────────────────────────────────────────────────

    def _get(self, endpoint: str):
        resp = self._s.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, payload):
        resp = self._s.post(f"{self.base_url}{endpoint}",
                            json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # ── public API methods ────────────────────────────────────────────────────

    def list_tasks(self):
        return self._get("/tasks")

    def list_results(self):
        return self._get("/results")

    def list_history(self):
        return self._get("/history")

    def add_task(self, title: str, task_type: str,
                 description: str = None, params: dict = None):
        """
        Build and POST a task payload that matches Tasks.post() in resources.py.

        Standard fields (title, description, task_type, status) are sent at the
        top level. Any extra key/value pairs in `params` are also sent at the top
        level — resources.py separates them into the `parameters` jsonb column
        automatically.
        """
        payload = {
            "title":     title,
            "task_type": task_type,
            "status":    "pending",
        }
        if description:
            payload["description"] = description
        if params:
            payload.update(params)   # e.g. command="whoami" or dwell=10

        # The API accepts a single object or a list; we send a single object
        return self._post("/tasks", payload)


# ─────────────────────────────────────────────────────────────────────────────
#  Argument parsing for the add-task inline command
# ─────────────────────────────────────────────────────────────────────────────

def parse_params(params_str: str) -> dict:
    """
    'command=whoami,timeout=5'  →  {'command': 'whoami', 'timeout': '5'}
    Handles values that contain spaces if quoted: command="ping google.com"
    """
    result = {}
    # Split on commas that are NOT inside quotes
    import re
    pairs = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', params_str)
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"'{pair}' is not key=value format")
        key, _, value = pair.partition("=")
        result[key.strip()] = value.strip().strip('"')
    return result


def parse_add_task_args(args: list[str]) -> dict:
    """Parse inline 'add-task --title T --tasktype X ...' arguments."""
    p = argparse.ArgumentParser(prog="add-task", add_help=False)
    p.add_argument("--title",    required=True)
    p.add_argument("--tasktype", required=True)
    p.add_argument("--desc",     default=None)
    p.add_argument("--params",   default=None,
                   help="Comma-separated key=value pairs")
    ns, unknown = p.parse_known_args(args)
    if unknown:
        raise ValueError(f"Unknown arguments: {unknown}")

    params = parse_params(ns.params) if ns.params else None
    return {
        "title":       ns.title,
        "task_type":   ns.tasktype,
        "description": ns.desc,
        "params":      params,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  REPL
# ─────────────────────────────────────────────────────────────────────────────

REPL_COMMANDS = [
    "list-tasks", "list-results", "list-history",
    "add-task", "help", "exit", "quit",
]

def run_repl(client: LPClient):
    if _RICH: console.print(BANNER, style="bold cyan")
    else: print(BANNER)

    info(f"Connected to listening post at {client.base_url}")
    info("Type 'help' for available commands\n")

    if _PT:
        session = PromptSession(
            history=InMemoryHistory(),
            auto_suggest=AutoSuggestFromHistory(),
            completer=WordCompleter(REPL_COMMANDS, ignore_case=True),
        )
        _input = lambda: session.prompt("operator> ")
    else:
        _input = lambda: input("operator> ")

    while True:
        try:
            line = _input().strip()
        except (KeyboardInterrupt, EOFError):
            print(); break

        if not line:
            continue

        parts = line.split()
        cmd   = parts[0].lower()
        args  = parts[1:]

        # ── dispatch ──────────────────────────────────────────────────────────
        try:
            if cmd in ("exit", "quit"):
                break

            elif cmd == "help":
                print(HELP_TEXT)

            elif cmd == "list-tasks":
                data = client.list_tasks()
                if not data:
                    warn("No tasks found.")
                else:
                    ok(f"{len(data)} task(s) found")
                    pretty(data, title="Tasks")

            elif cmd == "list-results":
                data = client.list_results()
                if not data:
                    warn("No results yet.")
                else:
                    ok(f"{len(data)} result(s) found")
                    pretty(data, title="Results")

            elif cmd == "list-history":
                data = client.list_history()
                if not data:
                    warn("History is empty.")
                else:
                    ok(f"{len(data)} history record(s) found")
                    pretty(data, title="History")

            elif cmd == "add-task":
                if not args:
                    err("Usage: add-task --title T --tasktype TYPE [--desc D] [--params k=v,k=v]")
                    continue
                try:
                    kwargs = parse_add_task_args(args)
                except (ValueError, SystemExit) as exc:
                    err(f"Bad arguments: {exc}")
                    continue

                data = client.add_task(**kwargs)
                ok("Task created:")
                pretty(data, title="New Task")

            else:
                err(f"Unknown command '{cmd}'. Type 'help'.")

        except (ConnectionError, Timeout):
            err(f"Lost connection to {client.base_url}. Is the listening post running?")
        except HTTPError as exc:
            err(f"HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:
            err(f"Unexpected error: {exc}")

    info("Goodbye.")

def main():
    p = argparse.ArgumentParser(description="Operator CLI — Listening Post Edition")
    p.add_argument("--server",  "-s", default=DEFAULT_SERVER,
                   help=f"Listening post URL (default: {DEFAULT_SERVER})")
    p.add_argument("--timeout", "-t", type=int, default=10,
                   help="Request timeout in seconds (default: 10)")
    a = p.parse_args()

    client = LPClient(a.server, timeout=a.timeout)

    try:
        client.list_tasks()   
    except (ConnectionError, Timeout):
        err(f"Cannot reach listening post at {a.server}. Is it running?")
        sys.exit(1)
    except HTTPError as exc:
        err(f"Listening post returned HTTP {exc.response.status_code}. Check your server.")
        sys.exit(1)

    run_repl(client)


if __name__ == "__main__":
    main()