# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.13.3"]
# ///
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import re
import sys
import tomllib
from typing import Any, Mapping

from merge_config import merge_config

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_ROLLED_BACK = 4


@dataclass(frozen=True)
class Asset:
    id: str
    kind: str
    category: str
    source: Path
    target: Path
    scope: str
    version: str
    upstream: str | None
    license: str | None
    last_reviewed: str | None
    requires: tuple[str, ...]


@dataclass(frozen=True)
class Context:
    root: Path
    manifest_path: Path
    harness_version: str
    minimum_codex_version: str
    codex_home: Path
    user_skills: Path
    user_bin: Path
    config_base: Path
    host_overlay: Path
    local_overlay: Path | None
    state_path: Path
    backups_dir: Path
    assets: tuple[Asset, ...]


@dataclass(frozen=True)
class AssetStatus:
    id: str
    category: str
    version: str
    source: str
    target: str
    status: str
    actual_target: str | None


_DEFAULT_VAR = re.compile(r"\$\{([A-Z_][A-Z0-9_]*):-([^}]+)\}")
_SIMPLE_VAR = re.compile(r"\$([A-Z_][A-Z0-9_]*)")


def expand_value(raw: str, env: Mapping[str, str]) -> str:
    def default_replace(match: re.Match[str]) -> str:
        name, fallback = match.groups()
        return env.get(name) or _SIMPLE_VAR.sub(
            lambda item: env.get(item.group(1), item.group(0)), fallback
        )

    value = _DEFAULT_VAR.sub(default_replace, raw)
    value = _SIMPLE_VAR.sub(lambda match: env.get(match.group(1), match.group(0)), value)
    if "$" in value:
        raise ValueError(f"unresolved variable in path: {raw}")
    return value


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_host(
    root: Path,
    host_dir: Path,
    explicit: str | None,
    env: Mapping[str, str],
) -> tuple[Path, Path | None]:
    del root
    name = explicit or env.get("CODEX_HELPER_HOST") or os.uname().nodename.split(".")[0].lower()
    tracked = host_dir / f"{name}.toml"
    if not tracked.exists():
        tracked = host_dir / "default.toml"
    local = host_dir / f"{name}.local.toml"
    return tracked, local if local.exists() else None


def load_context(
    root: Path,
    manifest_path: Path,
    host: str | None,
    env: Mapping[str, str],
) -> Context:
    data = tomllib.loads(manifest_path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema_version")
    paths = data["paths"]
    codex_home = Path(expand_value(paths["codex_home"], env)).expanduser()
    user_skills = Path(expand_value(paths["user_skills"], env)).expanduser()
    user_bin = Path(expand_value(paths["user_bin"], env)).expanduser()
    approved = (codex_home, user_skills, user_bin)
    assets: list[Asset] = []
    ids: set[str] = set()
    targets: set[Path] = set()
    for item in data.get("assets", []):
        source = (root / item["source"]).resolve()
        target = Path(expand_value(item["target"], env)).expanduser()
        if not is_within(source, root) or not source.exists():
            raise ValueError(f"invalid source for {item['id']}")
        if not any(is_within(target, allowed) for allowed in approved):
            raise ValueError(f"target outside approved roots: {target}")
        if item["id"] in ids or target in targets:
            raise ValueError("duplicate asset id or target")
        ids.add(item["id"])
        targets.add(target)
        assets.append(
            Asset(
                id=item["id"],
                kind=item["kind"],
                category=item["category"],
                source=source,
                target=target,
                scope=item["scope"],
                version=item["version"],
                upstream=item.get("upstream"),
                license=item.get("license"),
                last_reviewed=item.get("last_reviewed"),
                requires=tuple(item.get("requires", [])),
            )
        )
    config = data["config"]
    host_dir = (root / config["host_dir"]).resolve()
    tracked, local = select_host(root, host_dir, host, env)
    return Context(
        root=root.resolve(),
        manifest_path=manifest_path.resolve(),
        harness_version=data["harness_version"],
        minimum_codex_version=data["minimum_codex_version"],
        codex_home=codex_home,
        user_skills=user_skills,
        user_bin=user_bin,
        config_base=(root / config["base"]).resolve(),
        host_overlay=tracked,
        local_overlay=local,
        state_path=Path(expand_value(config["state"], env)).expanduser(),
        backups_dir=Path(expand_value(config["backups"], env)).expanduser(),
        assets=tuple(assets),
    )


def inspect_asset(asset: Asset) -> AssetStatus:
    if not asset.target.exists() and not asset.target.is_symlink():
        status, actual = "missing", None
    elif not asset.target.is_symlink():
        status, actual = "conflict", None
    else:
        actual_path = Path(os.readlink(asset.target))
        if not actual_path.is_absolute():
            actual_path = asset.target.parent / actual_path
        actual = str(actual_path.resolve(strict=False))
        if actual_path.resolve(strict=False) == asset.source.resolve(strict=False) and asset.target.exists():
            status = "current"
        elif not asset.target.exists():
            status = "broken"
        else:
            status = "drifted"
    return AssetStatus(
        asset.id,
        asset.category,
        asset.version,
        str(asset.source),
        str(asset.target),
        status,
        actual,
    )


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"managed_paths": [], "assets": {}}
    return json.loads(path.read_text())


def combined_overlay(context: Context) -> str:
    documents = [context.config_base.read_text(), context.host_overlay.read_text()]
    if context.local_overlay:
        documents.append(context.local_overlay.read_text())
    result = ""
    for document in documents:
        result = merge_config(result, document, previous_paths=()).text
    return result


def preview_config(context: Context) -> dict[str, Any]:
    live_path = context.codex_home / "config.toml"
    live_text = live_path.read_text() if live_path.exists() else ""
    state = read_state(context.state_path) if context.state_path.exists() else {"managed_paths": []}
    previous = tuple(tuple(path) for path in state.get("managed_paths", []))
    result = merge_config(live_text, combined_overlay(context), previous)
    return {
        "target": str(live_path),
        "status": "current" if result.text == live_text else "drifted",
        "managed_paths": [list(path) for path in result.managed_paths],
        "changes": result.text != live_text,
    }


def asset_record(asset: Asset, status: AssetStatus | None = None) -> dict[str, Any]:
    record = {
        "id": asset.id,
        "kind": asset.kind,
        "category": asset.category,
        "source": str(asset.source),
        "target": str(asset.target),
        "scope": asset.scope,
        "version": asset.version,
        "upstream": asset.upstream,
        "license": asset.license,
        "last_reviewed": asset.last_reviewed,
        "requires": list(asset.requires),
    }
    if status:
        record["status"] = status.status
        record["actual_target"] = status.actual_target
    return record


def command_plan(context: Context) -> tuple[dict[str, Any], int]:
    statuses = tuple(inspect_asset(asset) for asset in context.assets)
    config = preview_config(context)
    changes = [status.id for status in statuses if status.status != "current"]
    if config["changes"]:
        changes.append("config")
    return {
        "harness_version": context.harness_version,
        "host_overlay": str(context.host_overlay),
        "assets": [asset_record(asset, status) for asset, status in zip(context.assets, statuses)],
        "config": config,
        "changes": changes,
    }, EXIT_OK


def command_status(context: Context) -> tuple[dict[str, Any], int]:
    payload, _ = command_plan(context)
    return payload, EXIT_DRIFT if payload["changes"] else EXIT_OK


def command_inventory(context: Context) -> tuple[dict[str, Any], int]:
    return {
        "harness_version": context.harness_version,
        "host_overlay": str(context.host_overlay),
        "assets": [asset_record(asset, inspect_asset(asset)) for asset in context.assets],
    }, EXIT_OK


def command_list(context: Context, kind: str) -> tuple[dict[str, Any], int]:
    return {
        "harness_version": context.harness_version,
        "assets": [asset_record(asset, inspect_asset(asset)) for asset in context.assets if asset.category == kind],
    }, EXIT_OK


def command_version(context: Context, asset_id: str | None) -> tuple[dict[str, Any], int]:
    if asset_id is None:
        return {
            "harness_version": context.harness_version,
            "minimum_codex_version": context.minimum_codex_version,
        }, EXIT_OK
    for asset in context.assets:
        if asset.id == asset_id:
            return asset_record(asset), EXIT_OK
    raise ValueError(f"unknown asset id: {asset_id}")


def emit(payload: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-harness")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--host")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "status", "inventory"):
        child = sub.add_parser(name)
        child.add_argument("--json", action="store_true")
    list_parser = sub.add_parser("list")
    list_parser.add_argument(
        "--kind",
        choices=("skills", "agents", "profiles", "rules", "utilities"),
        required=True,
    )
    list_parser.add_argument("--json", action="store_true")
    version = sub.add_parser("version")
    version.add_argument("asset_id", nargs="?")
    version.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    manifest = args.manifest or root / "manifest.toml"
    try:
        context = load_context(root, manifest, args.host, os.environ)
        if args.command == "plan":
            payload, code = command_plan(context)
        elif args.command == "status":
            payload, code = command_status(context)
        elif args.command == "inventory":
            payload, code = command_inventory(context)
        elif args.command == "list":
            payload, code = command_list(context, args.kind)
        elif args.command == "version":
            payload, code = command_version(context, args.asset_id)
        else:
            parser.error(f"unsupported command: {args.command}")
        emit(payload, args.json)
        return code
    except (OSError, ValueError, KeyError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
