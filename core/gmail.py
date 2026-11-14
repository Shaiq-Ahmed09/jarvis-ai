"""Gmail Connector for J.A.R.V.I.S.
Deeply integrated with the official Antigravity Google Connector CLI (gmail) and native Windows browser tab opening.
Connected User: lucky090405@gmail.com
"""
import json
import os
import subprocess
import sys
import urllib.parse
import webbrowser
from pathlib import Path

GMAIL_COMPOSE_BASE = "https://mail.google.com/mail/?view=cm&fs=1"
GMAIL_SEARCH_BASE = "https://mail.google.com/mail/u/0/#search/"
GMAIL_INBOX_URL = "https://mail.google.com/mail/u/0/#inbox"

from core.browser import launch_browser_tab

def launch_browser_url(url: str):
    return launch_browser_tab(url)

def run_gmail_cli(args: list) -> tuple[str, str, int]:
    """Execute authenticated gmail CLI command."""
    try:
        cmd = ["gmail"] + args
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=20)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), 1

def open_inbox():
    """Visibly open Gmail inbox tab in user's default browser."""
    launch_browser_url(GMAIL_INBOX_URL)
    return "Opened your Gmail Inbox tab in your browser, Sir."

def compose_draft(to: str = "", subject: str = "", body: str = ""):
    """Create draft in Gmail via Google Connector AND open compose tab in browser."""
    params = {}
    if to: params["to"] = to
    if subject: params["su"] = subject
    if body: params["body"] = body
    web_url = GMAIL_COMPOSE_BASE + ("&" + urllib.parse.urlencode(params) if params else "")
    
    # Open the compose tab visibly for the user
    launch_browser_url(web_url)
    
    # Also save draft in cloud via Google Connector CLI
    cli_args = ["mutate", "create-draft"]
    if to: cli_args.extend(["--to", to])
    if subject: cli_args.extend(["--subject", subject])
    if body: cli_args.extend(["--body", body])
    stdout, stderr, code = run_gmail_cli(cli_args)
    
    if code == 0 and stdout:
        return f"Created draft in your Gmail account ({stdout}) and opened the compose tab for Sir's review."
    return f"Opened Gmail compose tab with draft for '{to or 'unspecified'}' in your browser, Sir."

def search_emails(query: str, max_results: int = 5):
    """Search messages using Google Connector CLI AND open the Gmail search tab."""
    search_url = GMAIL_SEARCH_BASE + urllib.parse.quote_plus(query or "")
    # Always open browser tab with the search results
    launch_browser_url(search_url)
    
    stdout, stderr, code = run_gmail_cli(["readonly", "search", query or "is:unread", "--max", str(max_results)])
    if code == 0 and stdout:
        return f"Opened Gmail search tab for '{query}'. Found matching emails:\n{stdout}"
    return f"Opened Gmail search tab for '{query}' in your browser, Sir."

def get_recent_emails(max_results: int = 5, open_tab: bool = True):
    """Retrieve recent unread emails via Google Connector CLI and optionally open the inbox."""
    if open_tab:
        launch_browser_url(GMAIL_INBOX_URL)
        
    stdout, stderr, code = run_gmail_cli(["readonly", "search", "is:unread", "--max", str(max_results)])
    if code == 0 and stdout:
        return f"Opened your inbox tab. Active unread emails for lucky090405@gmail.com:\n{stdout}"
    return "Opened your live Gmail Inbox in your browser, Sir."

def send_email(to: str, subject: str, body: str):
    """Send an email using Google Connector CLI."""
    if not to:
        return "Recipient email address is required to dispatch an email, Sir."
    cli_args = ["mutate", "send", "--to", to, "--subject", subject or "No Subject", "--body", body or ""]
    stdout, stderr, code = run_gmail_cli(cli_args)
    if code == 0:
        return f"Email successfully dispatched to {to} via Google Connector."
    else:
        # Fall back to opening draft in browser
        return compose_draft(to, subject, body)

def handle_gmail_tool(action: str, to: str = "", subject: str = "", body: str = "", query: str = "") -> str:
    act = (action or "open_inbox").lower()
    if act in ["compose", "create_draft", "draft"]:
        return compose_draft(to, subject, body)
    elif act in ["send", "send_email"]:
        return send_email(to, subject, body)
    elif act == "search":
        return search_emails(query)
    elif act in ["read", "read_recent", "check_inbox", "inbox"]:
        return get_recent_emails(open_tab=True)
    else:
        return open_inbox()
