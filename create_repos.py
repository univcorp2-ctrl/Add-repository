#!/usr/bin/env python3
"""Create GitHub repositories automatically from user-supplied names.

The user supplies one or more repository names (interactively or as CLI args).
For each name, the script infers a sensible description from common keywords
in the name and creates the repository on GitHub via the REST API.

Authentication: set the GITHUB_TOKEN environment variable to a personal
access token with the `repo` scope (or `public_repo` for public-only).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


GITHUB_API = "https://api.github.com"


PURPOSE_KEYWORDS: list[tuple[str, str]] = [
    ("api", "REST API service"),
    ("cli", "Command-line interface tool"),
    ("bot", "Automation bot"),
    ("web", "Web application"),
    ("app", "Application"),
    ("game", "Game project"),
    ("blog", "Blog / publishing site"),
    ("portfolio", "Personal portfolio site"),
    ("dashboard", "Dashboard / analytics UI"),
    ("chat", "Chat / messaging application"),
    ("ml", "Machine learning project"),
    ("ai", "AI / machine learning project"),
    ("data", "Data processing project"),
    ("scraper", "Web scraping tool"),
    ("crawler", "Web crawler"),
    ("server", "Backend server"),
    ("client", "Client application"),
    ("sdk", "Software development kit"),
    ("lib", "Reusable library"),
    ("library", "Reusable library"),
    ("plugin", "Plugin / extension"),
    ("extension", "Browser or editor extension"),
    ("test", "Tests / experimentation"),
    ("demo", "Demo project"),
    ("template", "Project template / boilerplate"),
    ("boilerplate", "Project template / boilerplate"),
    ("docs", "Documentation site"),
    ("notes", "Personal notes / knowledge base"),
    ("tool", "Utility tool"),
    ("util", "Utility helpers"),
    ("script", "Automation script"),
]


def humanize(name: str) -> str:
    """Turn 'my-cool-app' or 'my_cool_app' into 'My Cool App'."""
    words = re.split(r"[-_\s]+", name.strip())
    return " ".join(w.capitalize() for w in words if w)


def infer_description(name: str, override: str | None = None) -> str:
    """Infer a description from the repo name, or use the override if given."""
    if override:
        return override
    lowered = name.lower()
    tokens = set(re.split(r"[-_\s]+", lowered))
    purpose = None
    for keyword, label in PURPOSE_KEYWORDS:
        if keyword in tokens:
            purpose = label
            break
    title = humanize(name)
    if purpose:
        return f"{title} - {purpose}."
    return f"{title} - automatically created repository."


@dataclass
class RepoRequest:
    name: str
    description: str
    private: bool = False
    auto_init: bool = True


def parse_request_line(line: str) -> RepoRequest | None:
    """Parse one user input line.

    Accepted forms:
        my-repo
        my-repo: short description here
        my-repo (private): description
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    private = False
    m = re.match(r"^(\S+)\s*\(([^)]+)\)\s*(?::\s*(.+))?$", line)
    if m:
        name = m.group(1)
        flags = m.group(2).lower()
        desc = m.group(3)
        private = "private" in flags
    elif ":" in line:
        name, desc = line.split(":", 1)
        name = name.strip()
        desc = desc.strip()
    else:
        name = line
        desc = None

    if not re.match(r"^[A-Za-z0-9._-]+$", name):
        print(f"  ! skipping invalid repo name: {name!r}", file=sys.stderr)
        return None

    return RepoRequest(
        name=name,
        description=infer_description(name, desc),
        private=private,
    )


def github_request(token: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{GITHUB_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "auto-create-repos-script")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            payload = resp.read().decode() or "{}"
            return resp.status, json.loads(payload)
    except urllib.error.HTTPError as e:
        payload = e.read().decode() or "{}"
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = {"message": payload}
        return e.code, parsed


def get_authenticated_user(token: str) -> str | None:
    status, body = github_request(token, "GET", "/user")
    if status == 200:
        return body.get("login")
    print(f"  ! failed to identify user (HTTP {status}): {body.get('message')}", file=sys.stderr)
    return None


def create_repository(token: str, repo: RepoRequest) -> bool:
    body = {
        "name": repo.name,
        "description": repo.description,
        "private": repo.private,
        "auto_init": repo.auto_init,
    }
    status, response = github_request(token, "POST", "/user/repos", body)
    if status in (200, 201):
        url = response.get("html_url", f"(repo: {repo.name})")
        visibility = "private" if repo.private else "public"
        print(f"  + created {visibility} repo: {url}")
        print(f"      description: {repo.description}")
        return True
    print(
        f"  ! failed to create {repo.name!r} (HTTP {status}): "
        f"{response.get('message', 'unknown error')}",
        file=sys.stderr,
    )
    errors = response.get("errors") or []
    for err in errors:
        print(f"      - {err}", file=sys.stderr)
    return False


def collect_requests_interactive() -> list[RepoRequest]:
    print("Enter one repository per line. Examples:")
    print("    weather-app")
    print("    my-api: Backend service for orders")
    print("    secret-notes (private): Personal notes")
    print("Press Enter on a blank line (or Ctrl-D) to finish.\n")
    requests: list[RepoRequest] = []
    while True:
        try:
            line = input("repo> ")
        except EOFError:
            print()
            break
        if not line.strip():
            break
        parsed = parse_request_line(line)
        if parsed:
            requests.append(parsed)
    return requests


def collect_requests_from_args(items: list[str]) -> list[RepoRequest]:
    requests: list[RepoRequest] = []
    for item in items:
        parsed = parse_request_line(item)
        if parsed:
            requests.append(parsed)
    return requests


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create GitHub repositories automatically from a list of names."
    )
    parser.add_argument(
        "names",
        nargs="*",
        help='Repository names. Use "name: description" or "name (private): description" '
             "to override defaults. If omitted, the script reads from stdin or prompts.",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create all repositories as private (overridable per line via '(private)').",
    )
    parser.add_argument(
        "--no-init",
        action="store_true",
        help="Do not auto-initialise repositories with a README.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without calling the GitHub API.",
    )
    args = parser.parse_args()

    if args.names:
        requests = collect_requests_from_args(args.names)
    elif not sys.stdin.isatty():
        requests = []
        for line in sys.stdin:
            parsed = parse_request_line(line)
            if parsed:
                requests.append(parsed)
    else:
        requests = collect_requests_interactive()

    if args.private:
        for r in requests:
            r.private = True
    if args.no_init:
        for r in requests:
            r.auto_init = False

    if not requests:
        print("No repositories requested. Nothing to do.")
        return 0

    print(f"\nPlanned repositories ({len(requests)}):")
    for r in requests:
        visibility = "private" if r.private else "public"
        print(f"  - {r.name} [{visibility}]: {r.description}")

    if args.dry_run:
        print("\nDry run: no repositories were created.")
        return 0

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "\nError: GITHUB_TOKEN environment variable is not set.\n"
            "Create a personal access token with the 'repo' scope and export it:\n"
            "    export GITHUB_TOKEN=ghp_your_token_here",
            file=sys.stderr,
        )
        return 2

    user = get_authenticated_user(token)
    if not user:
        return 2
    print(f"\nAuthenticated as: {user}\n")

    successes = 0
    for r in requests:
        print(f"Creating {r.name!r}...")
        if create_repository(token, r):
            successes += 1

    print(f"\nDone. Created {successes}/{len(requests)} repositories.")
    return 0 if successes == len(requests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
