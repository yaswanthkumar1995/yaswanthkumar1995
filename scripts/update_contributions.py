#!/usr/bin/env python3
"""Fetch open source PRs and update the profile README dynamically."""

import json
import os
import re
import urllib.request

GITHUB_USER = "yaswanthkumar1995"
# Repos owned by the user are excluded (only contributions to other orgs count)
EXCLUDED_OWNERS = {GITHUB_USER.lower()}

README_PATH = "README.md"
START_MARKER = "<!-- CONTRIBUTIONS:START -->"
END_MARKER = "<!-- CONTRIBUTIONS:END -->"

# Badge colors per org
ORG_COLORS = {
    "kubeflow": "326CE5",
    "argoproj": "EF7B4D",
    "automattic": "5B2C6F",
    "modelcontextprotocol": "000000",
    "wordpress": "21759B",
    "anthropics": "D4A574",
}
DEFAULT_COLOR = "24292E"

# Logo overrides
ORG_LOGOS = {
    "kubeflow": "kubeflow",
    "argoproj": "argo",
    "wordpress": "wordpress",
    "kubernetes": "kubernetes",
    "anthropics": "anthropic",
}


def fetch_prs():
    """Fetch all PRs by the user across all repos using GitHub Search API."""
    token = os.environ.get("GH_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    prs = []
    page = 1
    while True:
        query = f"author:{GITHUB_USER}+type:pr"
        url = f"https://api.github.com/search/issues?q={query}&per_page=100&page={page}&sort=created&order=desc"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        prs.extend(data.get("items", []))
        if len(prs) >= data.get("total_count", 0) or not data.get("items"):
            break
        page += 1
    return prs


def group_by_repo(prs):
    """Group PRs by repo, excluding user-owned repos. Returns dict of repo -> {merged, open, closed, url, org}."""
    repos = {}
    for pr in prs:
        repo_url = pr.get("repository_url", "")
        # e.g. https://api.github.com/repos/argoproj/argo-cd
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 2:
            continue
        owner, repo = parts[-2], parts[-1]
        if owner.lower() in EXCLUDED_OWNERS:
            continue

        full_name = f"{owner}/{repo}"
        if full_name not in repos:
            repos[full_name] = {
                "owner": owner,
                "repo": repo,
                "merged": 0,
                "open": 0,
                "closed": 0,
                "url": f"https://github.com/{full_name}",
            }

        state = pr.get("state", "")
        if pr.get("pull_request", {}).get("merged_at"):
            repos[full_name]["merged"] += 1
        elif state == "open":
            repos[full_name]["open"] += 1
        else:
            repos[full_name]["closed"] += 1

    return repos


def make_badge(label, color, logo=None):
    """Create a shields.io badge URL."""
    label_enc = label.replace("-", "--").replace("_", "__").replace(" ", "_")
    badge_url = f"https://img.shields.io/badge/{label_enc}-{color}?style=for-the-badge&logoColor=white"
    if logo:
        badge_url += f"&logo={logo}"
    return badge_url


def build_table(repos):
    """Build the HTML table for the README."""
    if not repos:
        return "_No external contributions found yet._"

    # Sort: most total PRs first
    sorted_repos = sorted(
        repos.values(), key=lambda r: r["merged"] + r["open"] + r["closed"], reverse=True
    )

    rows = []
    cells = []

    for r in sorted_repos:
        owner = r["owner"]
        repo = r["repo"]
        display_name = repo.replace("-", " ").title()
        color = ORG_COLORS.get(owner.lower(), DEFAULT_COLOR)
        logo = ORG_LOGOS.get(owner.lower())
        badge = make_badge(display_name, color, logo)

        total = r["merged"] + r["open"] + r["closed"]
        parts = []
        if r["merged"]:
            parts.append(f'{r["merged"]} merged')
        if r["open"]:
            parts.append(f'{r["open"]} open')
        subtitle = ", ".join(parts) if parts else f"{total} PR{'s' if total != 1 else ''}"

        width = f'{100 // len(sorted_repos)}%' if sorted_repos else "20%"
        cell = (
            f'    <td align="center" width="{width}">\n'
            f'      <a href="{r["url"]}"><img src="{badge}"/></a>\n'
            f"      <br/><sub>{subtitle}</sub>\n"
            f"    </td>"
        )
        cells.append(cell)

    # Single row with all cells
    rows.append("  <tr>\n" + "\n".join(cells) + "\n  </tr>")

    return "<table>\n" + "\n".join(rows) + "\n</table>"


def update_readme(table_html):
    """Replace the section between markers in the README."""
    with open(README_PATH, "r") as f:
        content = f.read()

    pattern = re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER)
    replacement = f"{START_MARKER}\n{table_html}\n{END_MARKER}"
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    with open(README_PATH, "w") as f:
        f.write(new_content)

    return content != new_content


def main():
    print("Fetching PRs...")
    prs = fetch_prs()
    print(f"Found {len(prs)} total PRs")

    repos = group_by_repo(prs)
    print(f"Contributing to {len(repos)} external repos")
    for name, info in repos.items():
        print(f"  {name}: {info['merged']} merged, {info['open']} open, {info['closed']} closed")

    table = build_table(repos)
    changed = update_readme(table)

    if changed:
        print("README updated!")
    else:
        print("No changes needed.")


if __name__ == "__main__":
    main()
