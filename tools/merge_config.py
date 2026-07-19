from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import tomlkit
from tomlkit.exceptions import TOMLKitError

KeyPath = tuple[str, ...]


@dataclass(frozen=True)
class MergeResult:
    text: str
    managed_paths: tuple[KeyPath, ...]


def _leaf_paths(value: Any, prefix: KeyPath = ()) -> tuple[KeyPath, ...]:
    if isinstance(value, Mapping):
        if not value:
            return ()
        paths: list[KeyPath] = []
        for key, child in value.items():
            paths.extend(_leaf_paths(child, prefix + (str(key),)))
        return tuple(paths)
    return (prefix,)


def _remove_path(document: Any, path: KeyPath) -> None:
    parents: list[tuple[Any, str]] = []
    node = document
    for key in path[:-1]:
        if not isinstance(node, Mapping) or key not in node:
            return
        parents.append((node, key))
        node = node[key]
    if isinstance(node, Mapping):
        node.pop(path[-1], None)
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, Mapping) and not child:
            parent.pop(key, None)
        else:
            break


def _merge_table(destination: Any, source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, Mapping) and isinstance(destination.get(key), Mapping):
            _merge_table(destination[key], value)
        else:
            destination[key] = deepcopy(value)


def _parse(text: str, label: str):
    try:
        return tomlkit.parse(text or "")
    except TOMLKitError as error:
        raise ValueError(f"invalid {label} TOML: {error}") from error


def merge_config(
    live_text: str,
    overlay_text: str,
    previous_paths: Iterable[KeyPath],
) -> MergeResult:
    live = _parse(live_text, "live")
    overlay = _parse(overlay_text, "overlay")
    for path in sorted(tuple(previous_paths), key=len, reverse=True):
        if path:
            _remove_path(live, path)
    _merge_table(live, overlay)
    paths = tuple(sorted(_leaf_paths(overlay)))
    text = tomlkit.dumps(live)
    _parse(text, "merged")
    return MergeResult(text=text, managed_paths=paths)
