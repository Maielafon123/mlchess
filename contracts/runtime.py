"""Validate the complete wire schema before parsing generated Pydantic types."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, TypeVar

from jsonschema import Draft202012Validator
from pydantic import BaseModel
from referencing import Registry, Resource

from contracts.validate import CHECKER, ROOT

Model = TypeVar("Model", bound=BaseModel)


@lru_cache(maxsize=1)
def _bundle() -> tuple[dict, Registry]:
    schema = json.loads(
        (ROOT / "generated/validation.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(schema["$id"], Resource.from_contents(schema))
    return schema, registry


def parse_contract(model: type[Model], payload: Any) -> Model:
    """Raw generated models provide types; this boundary preserves if/then and formats."""
    schema, registry = _bundle()
    name = model.__name__
    if name not in schema["$defs"]:
        raise ValueError(f"Unknown public contract model: {name}")
    Draft202012Validator(
        {"$ref": schema["$id"] + "#/$defs/" + name},
        registry=registry,
        format_checker=CHECKER,
    ).validate(payload)
    return model.model_validate(payload)
