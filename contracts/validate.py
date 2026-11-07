"""Offline schema lint and golden-fixture validation for A-owned contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chess
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent
CHECKER = FormatChecker()


@CHECKER.checks("chess-fen", raises=ValueError)
def is_canonical_fen(value: Any) -> bool:
    if not isinstance(value, str):
        return True  # The schema's type keyword handles non-strings.
    board = chess.Board(value)
    return board.is_valid() and board.fen() == value


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys instead of silently discarding a constraint."""


def unique_mapping(loader: UniqueKeyLoader, node: Any) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def load_registry(root: Path = ROOT) -> tuple[Registry, dict[str, dict]]:
    schemas = {}
    for domain in ("common", "game"):
        path = root / domain / "v1.yaml"
        schema = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        Draft202012Validator.check_schema(schema)
        if schema["$id"] in schemas:
            raise ValueError(f"Duplicate schema id: {schema['$id']}")
        schemas[schema["$id"]] = schema
    # No retrieve callback: unknown references fail locally, with no network access.
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    resolver = registry.resolver()

    def check_references(value: Any) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                resolver.lookup(value["$ref"])
            for child in value.values():
                check_references(child)
        elif isinstance(value, list):
            for child in value:
                check_references(child)

    for schema in schemas.values():
        check_references(schema)
    return registry, schemas


def validator(
    schema_uri: str, registry: Registry | None = None
) -> Draft202012Validator:
    if registry is None:
        registry, _ = load_registry()
    return Draft202012Validator(
        {"$ref": schema_uri}, registry=registry, format_checker=CHECKER
    )


def check_snapshot_fixture(snapshot: dict) -> None:
    """Check golden examples against chess rules; not a production game service."""
    board = chess.Board()
    for ply, item in enumerate(snapshot["moves"], start=1):
        if item["ply"] != ply:
            raise ValueError("Fixture moves must have contiguous plies")
        move = chess.Move.from_uci(item["uci"])
        if move not in board.legal_moves:
            raise ValueError(f"Illegal fixture move at ply {ply}")
        if board.san(move) != item["san"]:
            raise ValueError(f"Incorrect fixture SAN at ply {ply}")
        board.push(move)
    if snapshot["ply"] != len(board.move_stack) or snapshot["fen"] != board.fen():
        raise ValueError("Fixture history does not match ply/FEN")
    if snapshot["side_to_move"] != ("white" if board.turn else "black"):
        raise ValueError("Fixture side_to_move disagrees with FEN")


def validate_fixtures(root: Path = ROOT) -> int:
    registry, _ = load_registry(root)
    fixtures = root / "fixtures"
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    paths = [entry["path"] for entry in manifest]
    # Manifest paths use stable POSIX separators on every platform.
    actual = {
        path.relative_to(fixtures).as_posix() for path in fixtures.rglob("*.json")
    }
    actual.discard("manifest.json")
    if len(paths) != len(set(paths)) or set(paths) != actual:
        raise ValueError("Fixture manifest must list every fixture exactly once")
    for entry in manifest:
        path = (fixtures / entry["path"]).resolve()
        if not path.is_relative_to(fixtures.resolve()):
            raise ValueError("Fixture path escapes fixture directory")
        payload = json.loads(path.read_text(encoding="utf-8"))
        validator(entry["schema"], registry).validate(payload)
        name = entry["schema"].rsplit("/", 1)[-1]
        if name == "GameSnapshotV1":
            check_snapshot_fixture(payload)
        elif name == "MoveAcceptedV1":
            check_snapshot_fixture(payload["snapshot"])
            if payload["move"] != payload["snapshot"]["moves"][-1]:
                raise ValueError("Accepted move differs from snapshot's last move")
    return len(manifest)


if __name__ == "__main__":
    count = validate_fixtures()
    print(f"Contract schemas and references valid; {count} golden fixtures passed.")
