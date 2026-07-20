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
    enabled: bool


@dataclass(frozen=True)
class Context:
    root: Path
    manifest_path: Path
    harness_version: str
    minimum_codex_version: str
    codex_home: Path
    config_home: Path
    user_skills: Path
    user_bin: Path
    config_source: Path
    config_default_source: Path
    config_host: str
    host_source: str
    host_fallback: bool
    state_path: Path
    preferences_path: Path
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


@dataclass(frozen=True)
class SkillPreferences:
    enabled: frozenset[str]
    disabled: frozenset[str]


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
    source_pattern: str,
    default_source: str,
    explicit: str | None,
    env: Mapping[str, str],
) -> tuple[Path, str, str, bool]:
    default_path = (root / default_source).resolve()
    if not is_within(default_path, root) or not default_path.is_file():
        raise ValueError("invalid default config source")
    configured = env.get("CODEX_HELPER_HOST")
    if explicit is not None:
        raw_name, origin, required = explicit, "explicit", True
    elif configured:
        raw_name, origin, required = configured, "environment", True
    else:
        raw_name, origin, required = os.uname().nodename, "hostname", False

    name = raw_name.split(".", 1)[0].lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name):
        if required:
            raise ValueError("host name must match [a-z0-9][a-z0-9_-]*")
        name = "default"
        selected = default_path
        fallback = True
    else:
        selected = (root / source_pattern.format(host=name)).resolve()
        fallback = not selected.is_file()
        if fallback:
            if required:
                raise ValueError(f"unknown host: {name}")
            selected = default_path
            name = "default"
    if not is_within(selected, root) or not selected.is_file():
        raise ValueError(f"invalid config source for host: {name}")
    return selected, name, origin, fallback


def load_context(
    root: Path,
    manifest_path: Path,
    host: str | None,
    env: Mapping[str, str],
) -> Context:
    data = tomllib.loads(manifest_path.read_text())
    if data.get("schema_version") != 2:
        raise ValueError("unsupported manifest schema_version")
    paths = data["paths"]
    codex_home = Path(expand_value(paths["codex_home"], env)).expanduser()
    config_home = Path(expand_value(paths["config_home"], env)).expanduser()
    user_skills = Path(expand_value(paths["user_skills"], env)).expanduser()
    user_bin = Path(expand_value(paths["user_bin"], env)).expanduser()
    approved = (codex_home, config_home, user_skills, user_bin)
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
        enabled = item.get("enabled", True)
        if "enabled" in item and item["category"] != "skills":
            raise ValueError(f"enabled is only supported for skills: {item['id']}")
        if not isinstance(enabled, bool):
            raise ValueError(f"enabled must be boolean for {item['id']}")
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
                enabled=enabled,
            )
        )
    config = data["config"]
    selected_config, config_host, host_source, host_fallback = select_host(
        root,
        config["source_pattern"],
        config["default_source"],
        host,
        env,
    )
    config_target = Path(expand_value(config["target"], env)).expanduser()
    if not is_lexically_within(config_target, config_home):
        raise ValueError(f"target outside approved roots: {config_target}")
    config_id = config["asset_id"]
    if config_id in ids or config_target in targets:
        raise ValueError("duplicate asset id or target")
    assets.append(
        Asset(
            id=config_id,
            kind="symlink",
            category="config",
            source=selected_config,
            target=config_target,
            scope="global",
            version=config["asset_version"],
            upstream=None,
            license=None,
            last_reviewed=None,
            requires=(),
            enabled=True,
        )
    )
    state_path = Path(expand_value(config["state"], env)).expanduser()
    preferences_path = Path(expand_value(config["preferences"], env)).expanduser()
    backups_dir = Path(expand_value(config["backups"], env)).expanduser()
    for name, path in (
        ("state", state_path),
        ("preferences", preferences_path),
        ("backups", backups_dir),
    ):
        if not is_lexically_within(path, config_home):
            raise ValueError(f"{name} path outside global config home: {path}")
    return Context(
        root=root.resolve(),
        manifest_path=manifest_path.resolve(),
        harness_version=data["harness_version"],
        minimum_codex_version=data["minimum_codex_version"],
        codex_home=codex_home,
        config_home=config_home,
        user_skills=user_skills,
        user_bin=user_bin,
        config_source=selected_config,
        config_default_source=(root / config["default_source"]).resolve(),
        config_host=config_host,
        host_source=host_source,
        host_fallback=host_fallback,
        state_path=state_path,
        preferences_path=preferences_path,
        backups_dir=backups_dir,
        assets=tuple(assets),
    )


def inspect_asset(asset: Asset, enabled: bool = True) -> AssetStatus:
    if not asset.target.exists() and not asset.target.is_symlink():
        status, actual = ("missing" if enabled else "disabled"), None
    elif not enabled:
        if _link_matches(asset.target, asset.source):
            status = "pending-disable"
            actual = str(asset.source.resolve(strict=False))
        else:
            status, actual = "conflict", None
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


def read_skill_preferences(context: Context) -> SkillPreferences:
    if not context.preferences_path.exists():
        return SkillPreferences(frozenset(), frozenset())
    data = tomllib.loads(context.preferences_path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported skill preferences schema_version")
    skills = data.get("skills", {})
    if not isinstance(skills, Mapping):
        raise ValueError("skills must be a table")
    enabled_raw = skills.get("enabled", [])
    disabled_raw = skills.get("disabled", [])
    if not isinstance(enabled_raw, list) or not all(isinstance(item, str) for item in enabled_raw):
        raise ValueError("skills.enabled must be a list of asset ids")
    if not isinstance(disabled_raw, list) or not all(isinstance(item, str) for item in disabled_raw):
        raise ValueError("skills.disabled must be a list of asset ids")
    enabled = frozenset(enabled_raw)
    disabled = frozenset(disabled_raw)
    if enabled & disabled:
        raise ValueError("skill preference cannot be both enabled and disabled")
    known = {asset.id for asset in context.assets if asset.category == "skills"}
    if not enabled | disabled <= known:
        raise ValueError("unknown or non-skill asset in skill preferences")
    return SkillPreferences(enabled, disabled)


def local_skill_override(asset: Asset, preferences: SkillPreferences) -> str | None:
    if asset.id in preferences.enabled:
        return "enabled"
    if asset.id in preferences.disabled:
        return "disabled"
    return None


def effective_enabled(asset: Asset, preferences: SkillPreferences) -> bool:
    override = local_skill_override(asset, preferences)
    if override == "enabled":
        return True
    if override == "disabled":
        return False
    return asset.enabled if asset.category == "skills" else True


def skill_preferences_text(preferences: SkillPreferences) -> str:
    enabled = ", ".join(json.dumps(item) for item in sorted(preferences.enabled))
    disabled = ", ".join(json.dumps(item) for item in sorted(preferences.disabled))
    return (
        "schema_version = 1\n\n[skills]\n"
        f"enabled = [{enabled}]\n"
        f"disabled = [{disabled}]\n"
    )


def write_skill_preferences(context: Context, preferences: SkillPreferences) -> None:
    atomic_write(
        context.preferences_path,
        skill_preferences_text(preferences).encode(),
        mode=0o600,
    )


def resolve_skill(context: Context, name: str) -> Asset:
    matches = [
        asset
        for asset in context.assets
        if asset.category == "skills"
        and (asset.id == name or asset.id.removeprefix("skill-") == name)
    ]
    if len(matches) != 1:
        raise ValueError(f"unknown or ambiguous skill: {name}")
    return matches[0]


def config_asset(context: Context) -> Asset:
    return next(asset for asset in context.assets if asset.category == "config")


def host_record(context: Context) -> dict[str, Any]:
    return {
        "name": context.config_host,
        "selection": context.host_source,
        "fallback": context.host_fallback,
    }


def asset_record(
    asset: Asset,
    status: AssetStatus | None = None,
    preferences: SkillPreferences | None = None,
) -> dict[str, Any]:
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
    if asset.category == "skills" and preferences is not None:
        record["default_enabled"] = asset.enabled
        record["local_override"] = local_skill_override(asset, preferences)
        record["effective_enabled"] = effective_enabled(asset, preferences)
    return record


def command_plan(context: Context) -> tuple[dict[str, Any], int]:
    preferences = read_skill_preferences(context)
    statuses = tuple(
        inspect_asset(asset, effective_enabled(asset, preferences)) for asset in context.assets
    )
    changes = [status.id for status in statuses if status.status not in {"current", "disabled"}]
    selected_config = config_asset(context)
    config_status = inspect_asset(selected_config)
    return {
        "harness_version": context.harness_version,
        "host": host_record(context),
        "host_overlay": str(context.config_source),
        "assets": [
            asset_record(asset, status, preferences)
            for asset, status in zip(context.assets, statuses)
        ],
        "config": {
            "source": str(selected_config.source),
            "target": str(selected_config.target),
            "status": config_status.status,
            "changes": config_status.status != "current",
        },
        "changes": changes,
    }, EXIT_OK


def command_status(context: Context) -> tuple[dict[str, Any], int]:
    payload, _ = command_plan(context)
    return payload, EXIT_DRIFT if payload["changes"] else EXIT_OK


def command_inventory(context: Context) -> tuple[dict[str, Any], int]:
    preferences = read_skill_preferences(context)
    return {
        "harness_version": context.harness_version,
        "host": host_record(context),
        "host_overlay": str(context.config_source),
        "assets": [
            asset_record(
                asset,
                inspect_asset(asset, effective_enabled(asset, preferences)),
                preferences,
            )
            for asset in context.assets
        ],
    }, EXIT_OK


def command_list(context: Context, kind: str) -> tuple[dict[str, Any], int]:
    preferences = read_skill_preferences(context)
    return {
        "harness_version": context.harness_version,
        "assets": [
            asset_record(
                asset,
                inspect_asset(asset, effective_enabled(asset, preferences)),
                preferences,
            )
            for asset in context.assets
            if asset.category == kind
        ],
    }, EXIT_OK


def command_version(context: Context, asset_id: str | None) -> tuple[dict[str, Any], int]:
    if asset_id is None:
        return {
            "harness_version": context.harness_version,
            "minimum_codex_version": context.minimum_codex_version,
        }, EXIT_OK
    for asset in context.assets:
        if asset.id == asset_id:
            return asset_record(asset, preferences=read_skill_preferences(context)), EXIT_OK
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


def _target_is_approved(context: Context, target: Path) -> bool:
    if not target.is_absolute():
        return False
    resolved_original_parent = target.parent.resolve(strict=False)
    absolute_target = Path(os.path.abspath(target))
    for root in (
        context.codex_home,
        context.config_home,
        context.user_skills,
        context.user_bin,
    ):
        absolute_root = Path(os.path.abspath(root))
        if absolute_target == absolute_root:
            continue
        if not is_lexically_within(absolute_target, absolute_root):
            continue
        if is_within(resolved_original_parent, absolute_root.resolve(strict=False)):
            return True
    return False


def validate_recorded_targets(context: Context, state: Mapping[str, Any]) -> None:
    records = state.get("assets", {})
    if not isinstance(records, Mapping):
        raise ValueError("state assets must be an object")
    for asset_id, record in records.items():
        if not isinstance(record, Mapping) or not isinstance(record.get("target"), str):
            raise ValueError(f"invalid recorded target for asset: {asset_id}")
        if not _target_is_approved(context, Path(record["target"])):
            raise ValueError(f"recorded target outside approved roots: {asset_id}")


def validate_receipt_targets(context: Context, receipt: Mapping[str, Any]) -> None:
    entries = receipt.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("snapshot entries must be a list")
    for entry in entries:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("target"), str):
            raise ValueError("invalid snapshot target")
        if not _target_is_approved(context, Path(entry["target"])):
            raise ValueError("snapshot target outside approved roots")


def _recorded_assets(context: Context, state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    validate_recorded_targets(context, state)
    state_records = state.get("assets", {})
    records: dict[str, dict[str, Any]] = {}
    for asset in context.assets:
        previous = state_records.get(asset.id, {})
        recorded_source = previous.get("source") if isinstance(previous, Mapping) else None
        records[asset.id] = {
            "source": recorded_source if isinstance(recorded_source, str) else str(asset.source),
            "target": str(asset.target),
            "kind": asset.kind,
            "category": asset.category,
            "version": asset.version,
        }
    current_ids = {asset.id for asset in context.assets}
    records.update(
        (key, dict(value))
        for key, value in state_records.items()
        if key not in current_ids
    )
    return records


def _snapshot_targets(context: Context, state: Mapping[str, Any]) -> list[Path]:
    targets = [Path(record["target"]) for record in _recorded_assets(context, state).values()]
    targets.extend((context.state_path, context.preferences_path))
    ordered: list[Path] = []
    seen: set[Path] = set()
    for target in targets:
        if target not in seen:
            seen.add(target)
            ordered.append(target)
    return ordered


def create_snapshot(context: Context, state: Mapping[str, Any]) -> dict[str, Any]:
    validate_recorded_targets(context, state)
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
        "host_overlay": str(context.config_source),
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
    validate_receipt_targets(context, receipt)
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


def build_state(context: Context) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "harness_version": context.harness_version,
        "host_overlay": str(context.config_source),
        "host": host_record(context),
        "managed_paths": [],
        "assets": {
            asset.id: {
                "source": str(asset.source),
                "target": str(asset.target),
                "kind": asset.kind,
                "category": asset.category,
                "version": asset.version,
                "enabled": asset.enabled,
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
    validate_recorded_targets(context, previous_state)
    preferences = read_skill_preferences(context)
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
    statuses = [
        inspect_asset(asset, effective_enabled(asset, preferences)) for asset in context.assets
    ]
    conflicts.extend(status.id for status in statuses if status.status == "conflict")
    config_rewire_requires_review = [
        status.id
        for asset, status in zip(context.assets, statuses)
        if asset.category == "config"
        and status.status in {"drifted", "broken", "conflict"}
    ]
    protected_conflicts = [
        status.id
        for asset, status in zip(context.assets, statuses)
        if status.status == "conflict" and not effective_enabled(asset, preferences)
    ]
    plan, _ = command_plan(context)
    if protected_conflicts or ((conflicts or config_rewire_requires_review) and not yes):
        return {
            **plan,
            "conflicts": list(dict.fromkeys(conflicts + config_rewire_requires_review)),
        }, EXIT_CONFLICT
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
            enabled = effective_enabled(asset, preferences)
            if status.status in {"current", "disabled"}:
                continue
            if not enabled and status.status == "pending-disable":
                asset.target.unlink()
                mutated()
                continue
            if asset.target.exists() or asset.target.is_symlink():
                _remove_existing(asset.target)
            atomic_symlink(asset.source, asset.target)
            mutated()
        state = build_state(context)
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
    selected_config = config_asset(context)
    records = _recorded_assets(context, state)
    for key, record in records.items():
        if key == selected_config.id:
            continue
        target, source = Path(record["target"]), Path(record["source"])
        if not target.exists() and not target.is_symlink():
            continue
        if _link_matches(target, source):
            target.unlink()
        else:
            conflicts.append(key)
    live_path = selected_config.target
    recorded_config = state.get("assets", {}).get(selected_config.id)
    if recorded_config:
        recorded_source = Path(recorded_config["source"])
        if not live_path.exists() and not live_path.is_symlink():
            pass
        elif _link_matches(live_path, recorded_source) and recorded_source.is_file():
            atomic_write(live_path, recorded_source.read_bytes(), mode=0o600)
        elif (
            live_path.is_file()
            and not live_path.is_symlink()
            and recorded_source.is_file()
            and live_path.read_bytes() == recorded_source.read_bytes()
        ):
            pass
        else:
            conflicts.append(selected_config.id)
    elif live_path.is_symlink():
        conflicts.append(selected_config.id)
    elif live_path.exists():
        # Backward compatibility for state written by the merge-based harness.
        live = live_path.read_text()
        previous = tuple(tuple(path) for path in state.get("managed_paths", []))
        cleaned = merge_config(live, "", previous).text
        atomic_write(live_path, cleaned.encode(), mode=0o600)
    if not conflicts and (context.state_path.exists() or context.state_path.is_symlink()):
        context.state_path.unlink()
    return {
        "snapshot_id": receipt["snapshot_id"],
        "unlinked": not conflicts,
        "conflicts": conflicts,
    }, EXIT_CONFLICT if conflicts else EXIT_OK


def command_bootstrap(context: Context) -> tuple[dict[str, Any], int]:
    directories = (
        context.codex_home,
        context.config_home,
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
    target = context.config_default_source.parent / f"config-{name}.toml"
    if target.exists():
        raise ValueError(f"host config already exists: {target}")
    atomic_write(target, context.config_default_source.read_bytes(), mode=0o644)
    return {"host": name, "path": str(target)}, EXIT_OK


def skill_record(
    asset: Asset,
    preferences: SkillPreferences,
) -> dict[str, Any]:
    return asset_record(
        asset,
        inspect_asset(asset, effective_enabled(asset, preferences)),
        preferences,
    )


def command_skill_list(context: Context) -> tuple[dict[str, Any], int]:
    preferences = read_skill_preferences(context)
    return {
        "harness_version": context.harness_version,
        "preferences": str(context.preferences_path),
        "skills": [
            skill_record(asset, preferences)
            for asset in context.assets
            if asset.category == "skills"
        ],
    }, EXIT_OK


def command_skill_status(context: Context, name: str) -> tuple[dict[str, Any], int]:
    preferences = read_skill_preferences(context)
    asset = resolve_skill(context, name)
    record = skill_record(asset, preferences)
    healthy = record["status"] in {"current", "disabled"}
    return record, EXIT_OK if healthy else EXIT_DRIFT


def command_skill_set(
    context: Context,
    name: str,
    action: str,
) -> tuple[dict[str, Any], int]:
    asset = resolve_skill(context, name)
    current = read_skill_preferences(context)
    enabled = set(current.enabled)
    disabled = set(current.disabled)
    if action == "enable":
        enabled.add(asset.id)
        disabled.discard(asset.id)
    elif action == "disable":
        disabled.add(asset.id)
        enabled.discard(asset.id)
    elif action == "reset":
        enabled.discard(asset.id)
        disabled.discard(asset.id)
    else:
        raise ValueError(f"unsupported skill action: {action}")
    updated = SkillPreferences(frozenset(enabled), frozenset(disabled))

    occupied = asset.target.exists() or asset.target.is_symlink()
    matching = _link_matches(asset.target, asset.source)
    if occupied and not matching:
        return {
            **skill_record(asset, current),
            "error": "skill target is occupied by an unowned object",
        }, EXIT_CONFLICT

    desired_enabled = effective_enabled(asset, updated)
    current_status = inspect_asset(asset, effective_enabled(asset, current)).status
    desired_status = inspect_asset(asset, desired_enabled).status
    preferences_changed = updated != current
    link_changed = desired_status not in {"current", "disabled"}
    if not preferences_changed and not link_changed:
        return {
            **skill_record(asset, updated),
            "action": action,
            "snapshot_id": None,
            "changed": False,
        }, EXIT_OK

    receipt = create_snapshot(context, read_state(context.state_path))
    fail_after = int(os.environ.get("CODEX_HELPER_SKILL_FAIL_AFTER", "0"))
    mutations = 0

    def mutated() -> None:
        nonlocal mutations
        mutations += 1
        if fail_after and mutations >= fail_after:
            raise RuntimeError("injected skill toggle failure")

    try:
        write_skill_preferences(context, updated)
        mutated()
        if desired_enabled and not matching:
            atomic_symlink(asset.source, asset.target)
            mutated()
        elif not desired_enabled and matching:
            asset.target.unlink()
            mutated()
    except Exception as error:
        restore_receipt(context, receipt)
        return {
            "snapshot_id": receipt["snapshot_id"],
            "rolled_back": True,
            "error": str(error),
        }, EXIT_ROLLED_BACK

    record = skill_record(asset, updated)
    return {
        **record,
        "action": action,
        "previous_status": current_status,
        "snapshot_id": receipt["snapshot_id"],
        "changed": True,
    }, EXIT_OK


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


_SENSITIVE_NAME = re.compile(
    r"(?:token(?![_-]?limit)|secret|password|credential|auth[_-]?key|api[_-]?key)",
    re.IGNORECASE,
)
_SENSITIVE_LITERAL = re.compile(r"authorization:\s*bearer\s+(?!REPLACE_ME\b)\S+", re.IGNORECASE)
_ASSIGNMENT = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.+?)\s*$"
)


def _operational_files(context: Context) -> tuple[Path, ...]:
    files = [context.root / "AGENTS.md", context.root / "manifest.toml"]
    for relative in ("bin", "tools", "sources"):
        base = context.root / relative
        files.extend(
            path
            for path in base.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
    return tuple(dict.fromkeys(files))


def _walk_sensitive_keys(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    findings: list[tuple[str, ...]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            current = path + (key_text,)
            if _SENSITIVE_NAME.search(key_text):
                if not (isinstance(child, str) and ("$" in child or child.startswith("env:"))):
                    findings.append(current)
            findings.extend(_walk_sensitive_keys(child, current))
    elif isinstance(value, list):
        for child in value:
            findings.extend(_walk_sensitive_keys(child, path))
    elif isinstance(value, str) and _SENSITIVE_LITERAL.search(value):
        findings.append(path or ("<value>",))
    return findings


def _secret_findings(context: Context) -> list[str]:
    findings: list[str] = []
    for path in _operational_files(context):
        relative = path.relative_to(context.root)
        try:
            if path.suffix == ".toml":
                data = tomllib.loads(path.read_text())
                keys = _walk_sensitive_keys(data)
            elif path.suffix == ".json":
                data = json.loads(path.read_text())
                keys = _walk_sensitive_keys(data)
            elif path.suffix in {".yaml", ".yml"}:
                keys = []
                for line in path.read_text().splitlines():
                    match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
                    if match and _SENSITIVE_NAME.search(match.group(1)):
                        value = match.group(2).strip()
                        if "$" not in value and not value.startswith("env:"):
                            keys.append((match.group(1),))
            elif path.suffix in {".py", ".sh", ".rules"} or path.parent.name == "bin":
                keys = []
                for line in path.read_text(errors="replace").splitlines():
                    match = _ASSIGNMENT.match(line)
                    if match and _SENSITIVE_NAME.search(match.group(1)):
                        value = match.group(2)
                        if "$" not in value and "os.environ" not in value and "getenv" not in value:
                            keys.append((match.group(1),))
            else:
                keys = []
        except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError):
            continue
        for key in keys:
            findings.append(f"{relative}:{'.'.join(key)}")
    return findings


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.search(r"(\d+(?:\.\d+)+)", value)
    if not match:
        raise ValueError("unable to parse Codex version")
    return tuple(int(part) for part in match.group(1).split("."))


def _config_source_paths(context: Context) -> tuple[Path, ...]:
    return tuple(sorted(context.config_default_source.parent.glob("config-*.toml")))


def _config_source_has_required_settings(data: Mapping[str, Any]) -> bool:
    if not all(isinstance(data.get(key), str) and data.get(key) for key in (
        "personality",
        "model",
        "model_reasoning_effort",
    )):
        return False
    features = data.get("features")
    agents = data.get("agents")
    if not isinstance(features, Mapping):
        return False
    if not isinstance(agents, Mapping):
        return False
    return (
        features.get("multi_agent") is True
        and isinstance(features.get("js_repl"), bool)
        and type(agents.get("max_threads")) is int
        and agents.get("max_threads") == 4
        and type(agents.get("max_depth")) is int
        and agents.get("max_depth") == 1
    )


def command_doctor(context: Context) -> tuple[dict[str, Any], int]:
    checks: list[dict[str, str]] = []

    def add(identifier: str, passed: bool, message: str) -> None:
        checks.append({"id": identifier, "status": "pass" if passed else "fail", "message": message})

    ids = [asset.id for asset in context.assets]
    targets = [asset.target for asset in context.assets]
    add(
        "manifest",
        len(ids) == len(set(ids))
        and len(targets) == len(set(targets))
        and all(asset.source.exists() for asset in context.assets),
        "manifest schema, sources, ids, targets, and approved roots are valid",
    )

    try:
        preferences = read_skill_preferences(context)
        preferences_ok = True
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        preferences = SkillPreferences(frozenset(), frozenset())
        preferences_ok = False
    add(
        "preferences",
        preferences_ok,
        "local skill preferences parse and reference known skill assets"
        if preferences_ok
        else "local skill preferences are invalid",
    )

    config_sources = _config_source_paths(context)
    toml_paths = list(config_sources)
    toml_paths.extend(asset.source for asset in context.assets if asset.category in {"agents", "profiles"})
    try:
        for path in toml_paths:
            tomllib.loads(path.read_text())
        add("toml", True, "managed TOML sources parse")
    except (OSError, tomllib.TOMLDecodeError):
        add("toml", False, "one or more managed TOML sources do not parse")

    config_sources_ok = bool(config_sources)
    try:
        config_sources_ok = config_sources_ok and all(
            _config_source_has_required_settings(tomllib.loads(path.read_text()))
            for path in config_sources
        )
    except (OSError, tomllib.TOMLDecodeError):
        config_sources_ok = False
    add(
        "config-sources",
        config_sources_ok,
        "all host configs are secret-free and contain required multi-agent keys"
        if config_sources_ok
        else "one or more host configs are missing required settings",
    )

    guidance = (context.root / "AGENTS.md").read_text()
    headings = (
        "Think Before Coding",
        "Simplicity First",
        "Surgical Changes",
        "Goal-Driven Execution",
        "Trade-off Reporting",
        "Harness Independence",
    )
    add("guidance", all(heading in guidance for heading in headings), "global guidance contract is present")

    skill_ok = True
    for asset in (item for item in context.assets if item.category == "skills"):
        skill_file = asset.source / "SKILL.md"
        if not skill_file.is_file():
            skill_ok = False
            continue
        text = skill_file.read_text()
        if "name:" not in text or "description:" not in text:
            skill_ok = False
        for reference in re.findall(r"(?:references|schemas|agents)/[A-Za-z0-9._/-]+", text):
            if not (asset.source / reference).exists():
                skill_ok = False
    add("skills", skill_ok, "managed skill metadata and local references are valid")

    agents_ok = True
    for asset in (item for item in context.assets if item.category == "agents"):
        try:
            data = tomllib.loads(asset.source.read_text())
            expected_sandbox_mode = (
                "workspace-write" if asset.id == "agent-developer" else "read-only"
            )
            agents_ok = agents_ok and all(
                data.get(key) for key in ("name", "description", "developer_instructions")
            ) and data.get("sandbox_mode") == expected_sandbox_mode
        except (OSError, tomllib.TOMLDecodeError):
            agents_ok = False
    add(
        "agents",
        agents_ok,
        "custom agents are named and use declared sandbox boundaries",
    )

    statuses = [
        inspect_asset(asset, effective_enabled(asset, preferences)) for asset in context.assets
    ]
    links_ok = all(status.status in {"current", "disabled"} for status in statuses)
    add(
        "links",
        links_ok,
        "all enabled links and disabled absences match declared state"
        if links_ok
        else "managed link drift detected",
    )

    config_ok = False
    try:
        state = read_state(context.state_path)
        selected_config = config_asset(context)
        recorded = state.get("assets", {}).get(selected_config.id, {})
        tomllib.loads(selected_config.source.read_text())
        config_ok = (
            _link_matches(selected_config.target, selected_config.source)
            and recorded.get("source") == str(selected_config.source)
            and recorded.get("target") == str(selected_config.target)
        )
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError):
        config_ok = False
    add(
        "config",
        config_ok,
        "live config links to the selected host source and matches state"
        if config_ok
        else "managed config link or selected host state drift detected",
    )

    flagged_sources = _secret_findings(context)
    add(
        "secrets",
        not flagged_sources,
        "no suspected secrets in managed sources"
        if not flagged_sources
        else "suspected secret key in managed source: " + ", ".join(flagged_sources),
    )

    forbidden = "/" + "claude" + "-harness-helper"
    source_ok = all(is_within(asset.source, context.root) for asset in context.assets)
    path_hits = []
    for path in _operational_files(context):
        try:
            if forbidden in path.read_text(errors="replace"):
                path_hits.append(str(path.relative_to(context.root)))
        except OSError:
            path_hits.append(str(path.relative_to(context.root)))
    self_contained = source_ok and not path_hits
    add(
        "self-contained",
        self_contained,
        "all operational sources are self-contained" if self_contained else "external harness path dependency detected",
    )

    try:
        version_output = subprocess.run(
            ["codex", "--version"], text=True, capture_output=True, check=True
        ).stdout
        version_ok = _version_tuple(version_output) >= _version_tuple(context.minimum_codex_version)
    except (OSError, ValueError, subprocess.CalledProcessError):
        version_ok = False
    add("codex-version", version_ok, "Codex CLI meets the minimum version" if version_ok else "Codex CLI is missing or too old")

    rules_source = next(
        (asset.source for asset in context.assets if asset.id == "rules-codex-helper"),
        None,
    )
    rules_ok = False
    if rules_source:
        try:
            result = subprocess.run(
                [
                    "codex",
                    "execpolicy",
                    "check",
                    "--pretty",
                    "--rules",
                    str(rules_source),
                    "codex-harness",
                    "status",
                ],
                text=True,
                capture_output=True,
            )
            rules_ok = result.returncode == 0 and '"decision": "allow"' in result.stdout
            if result.returncode != 0 and "execpolicy" in result.stderr.lower():
                rules_ok = True
        except OSError:
            rules_ok = True
    add("rules", rules_ok, "read-only harness command policy is valid" if rules_ok else "command policy validation failed")

    healthy = all(check["status"] == "pass" for check in checks)
    return {"health": "healthy" if healthy else "unhealthy", "checks": checks}, EXIT_OK if healthy else EXIT_DRIFT


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
    skill_parser = sub.add_parser("skill")
    skill_sub = skill_parser.add_subparsers(dest="skill_command", required=True)
    skill_list = skill_sub.add_parser("list")
    skill_list.add_argument("--json", action="store_true")
    for name in ("status", "enable", "disable", "reset"):
        child = skill_sub.add_parser(name)
        child.add_argument("name")
        child.add_argument("--json", action="store_true")
    external = sub.add_parser("external-review")
    external.add_argument("--repo", type=Path, required=True)
    external.add_argument("--cycle", type=int, default=1)
    external.add_argument("--evidence", type=Path)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    manifest = args.manifest or root / "manifest.toml"
    try:
        context_env: Mapping[str, str] = os.environ
        context_host = args.host
        if args.command == "host" and args.host_command == "init":
            context_env = {key: value for key, value in os.environ.items() if key != "CODEX_HELPER_HOST"}
            context_host = None
        context = load_context(root, manifest, context_host, context_env)
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
        elif args.command == "skill" and args.skill_command == "list":
            payload, code = command_skill_list(context)
        elif args.command == "skill" and args.skill_command == "status":
            payload, code = command_skill_status(context, args.name)
        elif args.command == "skill" and args.skill_command in {"enable", "disable", "reset"}:
            payload, code = command_skill_set(context, args.name, args.skill_command)
        elif args.command == "external-review":
            return command_external_review(context, args.repo, args.cycle, args.evidence)
        elif args.command == "doctor":
            payload, code = command_doctor(context)
        else:
            parser.error(f"unsupported command: {args.command}")
        emit(payload, getattr(args, "json", False))
        return code
    except (OSError, ValueError, KeyError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
