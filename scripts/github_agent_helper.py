#!/usr/bin/env python3
"""
GitHub Agent Helper CLI
Coordinates state machine transitions, issue ranking, and configuration for the ATB GitHub automation series.
"""

import argparse
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

STATE_FILE = Path(".github-agent-state.yml")
CONFIG_FILE = Path(".github-agent.yml")

def load_yaml(path: Path):
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"Warning: Failed to load {path}: {e}", file=sys.stderr)
        return {}

def save_yaml(path: Path, data: dict):
    try:
        import yaml
        tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent or ".", suffix=".tmp")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"Error saving {path}: {e}", file=sys.stderr)
        sys.exit(1)

def get_state():
    data = load_yaml(STATE_FILE)
    print(json.dumps(data, indent=2, ensure_ascii=False))

def set_state(state: str, key: str = None, value: str = None, json_data: str = None):
    data = load_yaml(STATE_FILE)
    data["state"] = state
    data["last_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if key and value is not None:
        data[key] = value
    if json_data:
        try:
            extra = json.loads(json_data)
            data.update(extra)
        except Exception as e:
            print(f"Error parsing json_data: {e}", file=sys.stderr)
            sys.exit(1)
    save_yaml(STATE_FILE, data)
    print(f"State updated to: {state}")

def rank_issues(input_stream):
    raw = input_stream.read()
    if not raw.strip():
        print("[]")
        return

    try:
        issues = json.loads(raw)
    except Exception as e:
        print(f"Error parsing issues JSON: {e}", file=sys.stderr)
        sys.exit(1)

    cfg = load_yaml(CONFIG_FILE)
    labels_cfg = cfg.get("labels", {})
    p_high = labels_cfg.get("priority_high", "priority: high").lower()
    bug_label = labels_cfg.get("bug", "bug").lower()

    # 1. Serial Gate: If ANY issue is currently in-progress, block
    in_progress = []
    for issue in issues:
        labels = [
            l.get("name", "").lower() if isinstance(l, dict) else str(l).lower()
            for l in (issue.get("labels") or [])
        ]
        if "in-progress" in labels:
            in_progress.append(issue)

    if in_progress:
        active = in_progress[0]
        print(
            f"SERIAL_GUARD_BLOCKED: Issue #{active.get('number')} (\"{active.get('title')}\") is already in-progress. Exiting to maintain serial execution.",
            file=sys.stderr,
        )
        print("[]")
        sys.exit(0)

    # 2. Filter backlog (skip in-pr)
    filtered = []
    for issue in issues:
        labels = [
            l.get("name", "").lower() if isinstance(l, dict) else str(l).lower()
            for l in (issue.get("labels") or [])
        ]
        if "in-pr" in labels:
            continue
        filtered.append(issue)

    def sort_key(issue):
        labels = [
            l.get("name", "").lower() if isinstance(l, dict) else str(l).lower()
            for l in (issue.get("labels") or [])
        ]
        is_high = 0 if p_high in labels else 1
        is_bug = 0 if bug_label in labels else 1
        num = issue.get("number") if issue.get("number") is not None else sys.maxsize
        return (is_high, is_bug, num)

    ranked = sorted(filtered, key=sort_key)
    print(json.dumps(ranked, indent=2, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser(description="GitHub Agent Helper")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("get-state")

    set_state_p = subparsers.add_parser("set-state")
    set_state_p.add_argument("--state", required=True, help="State name")
    set_state_p.add_argument("--key", help="State key to update")
    set_state_p.add_argument("--value", help="State value to update")
    set_state_p.add_argument("--json-data", help="JSON string of additional state keys")

    subparsers.add_parser("rank-issues")

    args = parser.parse_args()
    if args.command == "get-state":
        get_state()
    elif args.command == "set-state":
        set_state(args.state, args.key, args.value, args.json_data)
    elif args.command == "rank-issues":
        rank_issues(sys.stdin)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
