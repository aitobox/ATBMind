#!/usr/bin/env python3
"""
ATBMind Skills Management CLI
Command-line interface to manage, inspect, install, update, and bind skills.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path so it works seamlessly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from atbmind_core.skills import SkillManager, get_skill_registry
from atbmind_core.roles.registry import get_role_registry


def format_output(data: Any, is_json: bool = False, message: str = ""):
    if is_json:
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"result": data, "message": message}, indent=2, ensure_ascii=False))
    else:
        if message:
            print(message)
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"  {k}: {v}")
        elif isinstance(data, list):
            for item in data:
                print(f"  - {item}")
        elif data is not None and not message:
            print(str(data))


def cmd_list(manager: SkillManager, args: argparse.Namespace) -> int:
    manager.discover_all()
    manager.role_registry.scan_directory(manager.roles_dir)
    skills_map = manager.registry.get_all_skills()

    if args.role:
        role = manager.role_registry.get_role(args.role)
        if not role:
            print(f"Error: Role '{args.role}' not found.", file=sys.stderr)
            return 1
        bound_names = set(role.skills)
        skills_map = {k: v for k, v in skills_map.items() if k in bound_names}

    if args.json:
        result = []
        for name, s in sorted(skills_map.items()):
            result.append({
                "name": s.metadata.name,
                "version": s.metadata.version,
                "description": s.metadata.description,
                "tags": s.metadata.tags,
                "scope": s.scope,
                "source_type": s.source.source_type if s.source else "builtin",
                "bound_roles": s.metadata.bound_roles,
                "tools_count": len(s.tools),
            })
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print(f"Installed Skills ({len(skills_map)} total):")
    for name, s in sorted(skills_map.items()):
        source_badge = f"[{s.source.source_type if s.source else 'builtin'}]"
        scope_badge = f"({s.scope})"
        tools_info = f"{len(s.tools)} tool(s)"
        print(f"  • {name} (v{s.metadata.version}) {source_badge} {scope_badge} - {tools_info}")
        if s.metadata.description:
            print(f"    Description: {s.metadata.description}")
        if s.metadata.bound_roles:
            print(f"    Bound roles: {', '.join(s.metadata.bound_roles)}")
    return 0


def cmd_show(manager: SkillManager, args: argparse.Namespace) -> int:
    manager.discover_all()
    skill = manager.get_skill(args.skill)
    if not skill:
        print(f"Error: Skill '{args.skill}' not found.", file=sys.stderr)
        return 1

    req_info = manager.check_requirements(args.skill)

    details = {
        "name": skill.metadata.name,
        "version": skill.metadata.version,
        "description": skill.metadata.description,
        "tags": skill.metadata.tags,
        "author": skill.metadata.author,
        "repository": skill.metadata.repository,
        "enabled": skill.metadata.enabled,
        "bound_roles": skill.metadata.bound_roles,
        "scope": skill.scope,
        "skill_dir": skill.skill_dir,
        "source": skill.source.model_dump() if skill.source else None,
        "tools": [
            {
                "name": t.name,
                "description": t.description,
            }
            for t in skill.tools
        ],
        "requirements": req_info,
    }

    if args.json:
        print(json.dumps(details, indent=2, ensure_ascii=False))
        return 0

    print(f"Skill: {skill.metadata.name} (v{skill.metadata.version})")
    print(f"  Description: {skill.metadata.description}")
    print(f"  Scope:       {skill.scope} ({skill.skill_dir})")
    print(f"  Tags:        {', '.join(skill.metadata.tags)}")
    print(f"  Bound Roles: {', '.join(skill.metadata.bound_roles) or 'None'}")
    print(f"  Tools ({len(skill.tools)}):")
    for t in skill.tools:
        print(f"    - {t.name}: {t.description}")
    if req_info["has_requirements"]:
        print("  Requirements Status:")
        print(f"    Satisfied: {', '.join(req_info['satisfied']) or 'None'}")
        if req_info["missing"]:
            print(f"    MISSING:   {', '.join(req_info['missing'])}")
    return 0


def cmd_install(manager: SkillManager, args: argparse.Namespace) -> int:
    src = args.source.strip()
    try:
        if "github.com" in src or (not Path(src).exists() and "/" in src):
            skill = manager.import_from_github(
                url=src,
                target_scope=args.target,
                skill_name=args.name,
                overwrite=args.overwrite,
            )
        else:
            skill = manager.import_from_local(
                source_path=src,
                target_scope=args.target,
                skill_name=args.name,
                overwrite=args.overwrite,
            )
        if args.json:
            print(json.dumps({"success": True, "name": skill.metadata.name, "path": skill.skill_dir}, indent=2))
        else:
            print(f"Successfully installed skill '{skill.metadata.name}' to {skill.skill_dir}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            print(f"Error installing skill: {e}", file=sys.stderr)
        return 1


def cmd_new(manager: SkillManager, args: argparse.Namespace) -> int:
    try:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        skill = manager.create_skill(
            name=args.name,
            description=args.desc or "",
            tags=tags,
            with_tools=not args.no_tools,
            target_scope=args.target,
            author=args.author,
            overwrite=args.overwrite,
        )
        if args.json:
            print(json.dumps({"success": True, "name": skill.metadata.name, "path": skill.skill_dir}, indent=2))
        else:
            print(f"Successfully created skill scaffold '{skill.metadata.name}' at {skill.skill_dir}")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            print(f"Error creating skill: {e}", file=sys.stderr)
        return 1


def cmd_check(manager: SkillManager, args: argparse.Namespace) -> int:
    updates = manager.check_updates()
    if args.json:
        print(json.dumps(updates, indent=2, ensure_ascii=False))
        return 0

    print("Upstream Update Check Results:")
    if not updates:
        print("  No GitHub-sourced skills installed.")
        return 0

    for name, has_update in updates.items():
        status = "🔴 UPDATE AVAILABLE" if has_update else "✅ Up to date"
        print(f"  • {name}: {status}")
    return 0


def cmd_update(manager: SkillManager, args: argparse.Namespace) -> int:
    try:
        manager.discover_all()
        targets = []
        if args.all:
            updates = manager.check_updates()
            targets = [name for name, has_update in updates.items() if has_update]
            if not targets:
                if args.json:
                    print(json.dumps({"success": True, "updated": []}))
                else:
                    print("All GitHub skills are already up to date.")
                return 0
        elif args.skill:
            targets = [args.skill]
        else:
            print("Error: Specify a skill name or use --all.", file=sys.stderr)
            return 1

        updated_list = []
        for t in targets:
            s = manager.update_skill(t)
            updated_list.append(s.metadata.name)
            if not args.json:
                print(f"Successfully updated '{s.metadata.name}'")

        if args.json:
            print(json.dumps({"success": True, "updated": updated_list}))
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error updating skill: {e}", file=sys.stderr)
        return 1


def cmd_bind(manager: SkillManager, args: argparse.Namespace) -> int:
    try:
        manager.discover_all()
        manager.role_registry.scan_directory(manager.roles_dir)
        success = manager.bind_skill_to_role(args.role, args.skill)
        if args.json:
            print(json.dumps({"success": success, "role": args.role, "skill": args.skill}))
        else:
            print(f"Successfully bound skill '{args.skill}' to role '{args.role}'")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error binding skill: {e}", file=sys.stderr)
        return 1


def cmd_unbind(manager: SkillManager, args: argparse.Namespace) -> int:
    try:
        manager.discover_all()
        manager.role_registry.scan_directory(manager.roles_dir)
        success = manager.unbind_skill_from_role(args.role, args.skill)
        if args.json:
            print(json.dumps({"success": success, "role": args.role, "skill": args.skill}))
        else:
            print(f"Successfully unbound skill '{args.skill}' from role '{args.role}'")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error unbinding skill: {e}", file=sys.stderr)
        return 1


def cmd_remove(manager: SkillManager, args: argparse.Namespace) -> int:
    try:
        removed = manager.remove_skill(args.skill, scope=args.target)
        if not removed:
            if args.json:
                print(json.dumps({"success": False, "error": f"Skill '{args.skill}' not found"}))
            else:
                print(f"Skill '{args.skill}' not found.", file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps({"success": True, "removed": args.skill}))
        else:
            print(f"Successfully removed skill '{args.skill}'")
        return 0
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"Error removing skill: {e}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="atbmind_skills",
        description="ATBMind Skills Management CLI",
    )
    parser.add_argument("--project-dir", help="Custom project skills directory path")
    parser.add_argument("--global-dir", help="Custom global skills directory path")
    parser.add_argument("--roles-dir", help="Custom roles directory path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. list
    p_list = subparsers.add_parser("list", help="List installed skills")
    p_list.add_argument("--role", help="Filter skills bound to a specific role")
    p_list.add_argument("--json", action="store_true", help="Output in JSON format")

    # 2. show
    p_show = subparsers.add_parser("show", help="Show details of a skill")
    p_show.add_argument("skill", help="Skill identifier name")
    p_show.add_argument("--json", action="store_true", help="Output in JSON format")

    # 3. install
    p_install = subparsers.add_parser("install", help="Install a skill from GitHub or local path")
    p_install.add_argument("source", help="GitHub URL or local path or zip file")
    p_install.add_argument("--target", choices=["global", "project"], default="global", help="Installation scope")
    p_install.add_argument("--name", help="Custom destination skill name")
    p_install.add_argument("--overwrite", action="store_true", help="Overwrite existing skill")
    p_install.add_argument("--json", action="store_true", help="Output in JSON format")

    # 4. new
    p_new = subparsers.add_parser("new", help="Create a new standardized skill package")
    p_new.add_argument("name", help="New skill identifier name")
    p_new.add_argument("--desc", help="Short description")
    p_new.add_argument("--tags", help="Comma-separated tags")
    p_new.add_argument("--no-tools", action="store_true", help="Do not create tools.py")
    p_new.add_argument("--author", help="Author name")
    p_new.add_argument("--target", choices=["global", "project"], default="global", help="Destination scope")
    p_new.add_argument("--overwrite", action="store_true", help="Overwrite if directory exists")
    p_new.add_argument("--json", action="store_true", help="Output in JSON format")

    # 5. check
    p_check = subparsers.add_parser("check", help="Check upstream updates on GitHub skills")
    p_check.add_argument("--json", action="store_true", help="Output in JSON format")

    # 6. update
    p_update = subparsers.add_parser("update", help="Update GitHub skills")
    p_update.add_argument("skill", nargs="?", help="Skill identifier to update")
    p_update.add_argument("--all", action="store_true", help="Update all skills with available updates")
    p_update.add_argument("--json", action="store_true", help="Output in JSON format")

    # 7. bind
    p_bind = subparsers.add_parser("bind", help="Bind a skill to a RobotRole expert")
    p_bind.add_argument("role", help="Role ID")
    p_bind.add_argument("skill", help="Skill name")
    p_bind.add_argument("--json", action="store_true", help="Output in JSON format")

    # 8. unbind
    p_unbind = subparsers.add_parser("unbind", help="Unbind a skill from a RobotRole expert")
    p_unbind.add_argument("role", help="Role ID")
    p_unbind.add_argument("skill", help="Skill name")
    p_unbind.add_argument("--json", action="store_true", help="Output in JSON format")

    # 9. remove
    p_remove = subparsers.add_parser("remove", help="Remove an installed skill")
    p_remove.add_argument("skill", help="Skill name")
    p_remove.add_argument("--target", choices=["global", "project"], help="Specific scope to delete from")
    p_remove.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    manager = SkillManager(
        project_dir=args.project_dir,
        global_dir=args.global_dir,
        roles_dir=args.roles_dir,
    )

    handlers = {
        "list": cmd_list,
        "show": cmd_show,
        "install": cmd_install,
        "new": cmd_new,
        "check": cmd_check,
        "update": cmd_update,
        "bind": cmd_bind,
        "unbind": cmd_unbind,
        "remove": cmd_remove,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(manager, args)


if __name__ == "__main__":
    sys.exit(main())
