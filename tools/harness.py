# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.13.3"]
# ///
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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


def is_lexically_within(path: Path, root: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root)))
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
        if not any(is_lexically_within(target, allowed) for allowed in approved):
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


def _toml_semantically_equal(left: str, right: str) -> bool:
    return tomllib.loads(left or "") == tomllib.loads(right or "")


def preview_config(context: Context) -> dict[str, Any]:
    live_path = context.codex_home / "config.toml"
    live_text = live_path.read_text() if live_path.exists() else ""
    state = read_state(context.state_path) if context.state_path.exists() else {"managed_paths": []}
    previous = tuple(tuple(path) for path in state.get("managed_paths", []))
    result = merge_config(live_text, combined_overlay(context), previous)
    changes = not _toml_semantically_equal(result.text, live_text)
    return {
        "target": str(live_path),
        "status": "drifted" if changes else "current",
        "managed_paths": [list(path) for path in result.managed_paths],
        "changes": changes,
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


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def new_snapshot_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_target(target: Path, snapshot_dir: Path) -> dict[str, Any]:
    entry: dict[str, Any] = {"target": str(target), "type": "missing"}
    if target.is_symlink():
        entry.update(type="symlink", link=os.readlink(target))
    elif target.is_file():
        relative = Path("files") / hashlib.sha256(str(target).encode()).hexdigest()
        destination = snapshot_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
        entry.update(type="file", backup=str(relative), sha256=sha256(target))
    elif target.is_dir():
        relative = Path("dirs") / hashlib.sha256(str(target).encode()).hexdigest()
        shutil.copytree(target, snapshot_dir / relative, symlinks=True)
        entry.update(type="directory", backup=str(relative))
    return entry


def _recorded_assets(context: Context, state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    records = {key: dict(value) for key, value in state.get("assets", {}).items()}
    for asset in context.assets:
        records[asset.id] = {
            "source": str(asset.source),
            "target": str(asset.target),
            "kind": asset.kind,
            "category": asset.category,
            "version": asset.version,
        }
    return records


def _snapshot_targets(context: Context, state: Mapping[str, Any]) -> list[Path]:
    targets = [Path(record["target"]) for record in _recorded_assets(context, state).values()]
    targets.extend((context.codex_home / "config.toml", context.state_path))
    ordered: list[Path] = []
    seen: set[Path] = set()
    for target in targets:
        if target not in seen:
            seen.add(target)
            ordered.append(target)
    return ordered


def create_snapshot(context: Context, state: Mapping[str, Any]) -> dict[str, Any]:
    snapshot_id = new_snapshot_id()
    snapshot_dir = context.backups_dir / snapshot_id
    counter = 1
    while snapshot_dir.exists():
        snapshot_dir = context.backups_dir / f"{snapshot_id}-{counter}"
        counter += 1
    snapshot_id = snapshot_dir.name
    snapshot_dir.mkdir(parents=True)
    try:
        revision = subprocess.run(
            ["git", "-C", str(context.root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unknown"
    receipt = {
        "snapshot_id": snapshot_id,
        "harness_version": context.harness_version,
        "git_revision": revision,
        "host_overlay": str(context.host_overlay),
        "entries": [backup_target(target, snapshot_dir) for target in _snapshot_targets(context, state)],
    }
    atomic_write(
        snapshot_dir / "receipt.json",
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(),
    )
    return receipt


def _remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def restore_receipt(context: Context, receipt: Mapping[str, Any]) -> None:
    snapshot_dir = context.backups_dir / str(receipt["snapshot_id"])
    for entry in reversed(receipt["entries"]):
        target = Path(entry["target"])
        _remove_existing(target)
        kind = entry["type"]
        if kind == "missing":
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind == "symlink":
            target.symlink_to(entry["link"])
        elif kind == "file":
            shutil.copy2(snapshot_dir / entry["backup"], target)
        elif kind == "directory":
            shutil.copytree(snapshot_dir / entry["backup"], target, symlinks=True)
        else:
            raise ValueError(f"unknown snapshot entry type: {kind}")


def atomic_symlink(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.codex-helper-tmp"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(source)
    os.replace(temporary, target)


def apply_config(
    context: Context,
    previous_state: Mapping[str, Any],
) -> tuple[str, tuple[tuple[str, ...], ...]]:
    live_path = context.codex_home / "config.toml"
    live_text = live_path.read_text() if live_path.exists() else ""
    previous = tuple(tuple(path) for path in previous_state.get("managed_paths", []))
    result = merge_config(live_text, combined_overlay(context), previous)
    output = live_text if _toml_semantically_equal(result.text, live_text) else result.text
    if output != live_text or not live_path.exists():
        atomic_write(live_path, output.encode(), mode=0o600)
    return output, result.managed_paths


def build_state(
    context: Context,
    managed_paths: tuple[tuple[str, ...], ...],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "harness_version": context.harness_version,
        "host_overlay": str(context.host_overlay),
        "managed_paths": [list(path) for path in managed_paths],
        "assets": {
            asset.id: {
                "source": str(asset.source),
                "target": str(asset.target),
                "kind": asset.kind,
                "category": asset.category,
                "version": asset.version,
            }
            for asset in context.assets
        },
    }


def _link_matches(target: Path, source: Path) -> bool:
    if not target.is_symlink():
        return False
    actual = Path(os.readlink(target))
    if not actual.is_absolute():
        actual = target.parent / actual
    return actual.resolve(strict=False) == source.resolve(strict=False)


def command_snapshot(context: Context) -> tuple[dict[str, Any], int]:
    receipt = create_snapshot(context, read_state(context.state_path))
    return receipt, EXIT_OK


def command_restore(
    context: Context,
    snapshot_id: str,
    yes: bool,
) -> tuple[dict[str, Any], int]:
    if not yes:
        return {"error": "restore requires --yes"}, EXIT_CONFLICT
    snapshot_dir = context.backups_dir / snapshot_id
    if not is_within(snapshot_dir, context.backups_dir):
        raise ValueError("invalid snapshot id")
    receipt_path = snapshot_dir / "receipt.json"
    if not receipt_path.is_file():
        raise ValueError(f"snapshot not found: {snapshot_id}")
    receipt = json.loads(receipt_path.read_text())
    restore_receipt(context, receipt)
    return {"snapshot_id": snapshot_id, "restored": True}, EXIT_OK


def command_apply(context: Context, yes: bool) -> tuple[dict[str, Any], int]:
    previous_state = read_state(context.state_path)
    current_ids = {asset.id for asset in context.assets}
    stale = {
        key: record
        for key, record in previous_state.get("assets", {}).items()
        if key not in current_ids
    }
    conflicts = []
    removable_stale = []
    for key, record in stale.items():
        target, source = Path(record["target"]), Path(record["source"])
        if not target.exists() and not target.is_symlink():
            continue
        if _link_matches(target, source):
            removable_stale.append((key, target))
        else:
            conflicts.append(key)
    statuses = [inspect_asset(asset) for asset in context.assets]
    conflicts.extend(status.id for status in statuses if status.status == "conflict")
    plan, _ = command_plan(context)
    if conflicts and not yes:
        return {**plan, "conflicts": conflicts}, EXIT_CONFLICT
    if not plan["changes"] and not removable_stale:
        return {**plan, "snapshot_id": None, "applied": False}, EXIT_OK
    receipt = create_snapshot(context, previous_state)
    fail_after = int(os.environ.get("CODEX_HELPER_FAIL_AFTER", "0"))
    mutations = 0

    def mutated() -> None:
        nonlocal mutations
        mutations += 1
        if fail_after and mutations >= fail_after:
            raise RuntimeError("injected apply failure")

    try:
        for _, target in removable_stale:
            target.unlink()
            mutated()
        for asset, status in zip(context.assets, statuses):
            if status.status == "current":
                continue
            if asset.target.exists() or asset.target.is_symlink():
                _remove_existing(asset.target)
            atomic_symlink(asset.source, asset.target)
            mutated()
        _, managed_paths = apply_config(context, previous_state)
        mutated()
        state = build_state(context, managed_paths)
        atomic_write(
            context.state_path,
            (json.dumps(state, indent=2, sort_keys=True) + "\n").encode(),
        )
        mutated()
    except Exception as error:
        restore_receipt(context, receipt)
        return {
            "snapshot_id": receipt["snapshot_id"],
            "rolled_back": True,
            "error": str(error),
        }, EXIT_ROLLED_BACK
    return {
        "snapshot_id": receipt["snapshot_id"],
        "applied": True,
        "conflicts_replaced": conflicts,
    }, EXIT_OK


def command_unlink(context: Context, yes: bool) -> tuple[dict[str, Any], int]:
    if not yes:
        return {"error": "unlink requires --yes"}, EXIT_CONFLICT
    state = read_state(context.state_path)
    receipt = create_snapshot(context, state)
    conflicts: list[str] = []
    for key, record in _recorded_assets(context, state).items():
        target, source = Path(record["target"]), Path(record["source"])
        if not target.exists() and not target.is_symlink():
            continue
        if _link_matches(target, source):
            target.unlink()
        else:
            conflicts.append(key)
    live_path = context.codex_home / "config.toml"
    if live_path.exists():
        live = live_path.read_text()
        previous = tuple(tuple(path) for path in state.get("managed_paths", []))
        cleaned = merge_config(live, "", previous).text
        atomic_write(live_path, cleaned.encode(), mode=0o600)
    if context.state_path.exists() or context.state_path.is_symlink():
        context.state_path.unlink()
    return {
        "snapshot_id": receipt["snapshot_id"],
        "unlinked": not conflicts,
        "conflicts": conflicts,
    }, EXIT_CONFLICT if conflicts else EXIT_OK


def command_bootstrap(context: Context) -> tuple[dict[str, Any], int]:
    directories = (
        context.codex_home,
        context.user_skills,
        context.user_bin,
        context.codex_home / "agents",
        context.codex_home / "rules",
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "created": [str(path) for path in directories],
        "next": f"Ensure {context.user_bin} is on PATH, apply the harness, then restart Codex.",
    }, EXIT_OK


def command_host_init(context: Context, name: str) -> tuple[dict[str, Any], int]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        raise ValueError("host name must match [a-z0-9][a-z0-9_-]*")
    target = context.config_base.parent / "hosts" / f"{name}.toml"
    if target.exists():
        raise ValueError(f"host overlay already exists: {target}")
    text = (
        f"# Host-specific non-secret Codex settings for {name}.\n"
        "# Keep secrets in environment variables or Codex credential storage.\n"
    )
    atomic_write(target, text.encode(), mode=0o644)
    return {"host": name, "path": str(target)}, EXIT_OK


def command_external_review(
    context: Context,
    repo: Path,
    cycle: int,
    evidence: Path | None,
) -> int:
    if cycle < 1 or cycle > 3:
        print("ERROR: cycle must be between 1 and 3", file=sys.stderr)
        return EXIT_USAGE
    if not (repo / ".git").exists():
        print("ERROR: --repo must be a Git repository", file=sys.stderr)
        return EXIT_USAGE
    skill = context.root / "sources/skills/dual-loop-review"
    prompt = (skill / "references/reviewer-prompt.md").read_text()
    if evidence:
        prompt += "\n\nVerification evidence:\n" + evidence.read_text()
    schema = skill / "schemas/verdict.schema.json"
    with tempfile.TemporaryDirectory(prefix="codex-external-review-") as temp:
        output = Path(temp) / "verdict.json"
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--profile",
            "deep-review",
            "--cd",
            str(repo.resolve()),
            "--output-schema",
            str(schema),
            "--output-last-message",
            str(output),
            "-",
        ]
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True)
        if completed.returncode != 0:
            print(completed.stderr, file=sys.stderr, end="")
            return EXIT_DRIFT
        payload = json.loads(output.read_text())
        allowed = {"pass", "changes_requested", "blocked"}
        if payload.get("verdict") not in allowed:
            print("ERROR: invalid external review verdict", file=sys.stderr)
            return EXIT_DRIFT
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_OK


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
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--yes", action="store_true")
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--json", action="store_true")
    restore = sub.add_parser("restore")
    restore.add_argument("snapshot_id")
    restore.add_argument("--yes", action="store_true")
    unlink = sub.add_parser("unlink")
    unlink.add_argument("--yes", action="store_true")
    sub.add_parser("bootstrap")
    host_parser = sub.add_parser("host")
    host_sub = host_parser.add_subparsers(dest="host_command", required=True)
    host_init = host_sub.add_parser("init")
    host_init.add_argument("name")
    external = sub.add_parser("external-review")
    external.add_argument("--repo", type=Path, required=True)
    external.add_argument("--cycle", type=int, default=1)
    external.add_argument("--evidence", type=Path)
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
        elif args.command == "apply":
            payload, code = command_apply(context, args.yes)
        elif args.command == "snapshot":
            payload, code = command_snapshot(context)
        elif args.command == "restore":
            payload, code = command_restore(context, args.snapshot_id, args.yes)
        elif args.command == "unlink":
            payload, code = command_unlink(context, args.yes)
        elif args.command == "bootstrap":
            payload, code = command_bootstrap(context)
        elif args.command == "host" and args.host_command == "init":
            payload, code = command_host_init(context, args.name)
        elif args.command == "external-review":
            return command_external_review(context, args.repo, args.cycle, args.evidence)
        else:
            parser.error(f"unsupported command: {args.command}")
        emit(payload, getattr(args, "json", False))
        return code
    except (OSError, ValueError, KeyError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
