from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest
import yaml
from jsonschema import ValidationError
from openapi_spec_validator import validate as validate_openapi

from backend.app.infra.generated import contracts as models
from contracts.runtime import parse_contract
from contracts.tooling.build import assemble, render
from contracts.tooling.compatibility import compare_specs
from contracts.tooling.generate import generate
from contracts.validate import ROOT

MANIFEST = json.loads((ROOT / "fixtures/manifest.json").read_text())


def sample(path):
    return json.loads((ROOT / "fixtures" / (path + ".json")).read_text())


@pytest.mark.parametrize("entry", MANIFEST, ids=lambda entry: entry["path"])
def test_all_golden_fixtures_roundtrip_through_pydantic(entry):
    payload = json.loads((ROOT / "fixtures" / entry["path"]).read_text())
    name = entry["schema"].rsplit("/", 1)[-1]
    parsed = parse_contract(getattr(models, name), payload)
    assert parsed.model_dump(mode="json", exclude_unset=True) == payload


@pytest.mark.parametrize(
    "name,path,mutate",
    [
        ("CreateGameV1", "game/create-coach", lambda x: x.pop("human_color")),
        ("CreateGameV1", "game/create-coach", lambda x: x.update(mode="rated")),
        ("GameSnapshotV1", "game/snapshot-coach", lambda x: x.pop("clock")),
        ("AnalysisResultV1", "analysis/result-mate", lambda x: x.update(cp_loss=100)),
        ("SubmitMoveV1", "game/submit-move", lambda x: x.update(expected_version=True)),
        ("AnalysisJobV1", "analysis/job-pending", lambda x: x.pop("analysis_id")),
        (
            "AnalysisRequestV1",
            "analysis/request-quick",
            lambda x: x.update(engine_path="/bin/sh"),
        ),
        (
            "CurrentUserV1",
            "common/current-guest",
            lambda x: x.update(expires_at="2026-02-30T14:00:00Z"),
        ),
    ],
)
def test_schema_boundary_retains_conditions_and_formats_missing_from_codegen(
    name, path, mutate
):
    payload = sample(path)
    mutate(payload)
    with pytest.raises(ValidationError):
        parse_contract(getattr(models, name), payload)


@pytest.fixture(scope="module")
def spec():
    return assemble()


def test_assembled_openapi_valid_and_matches_generated_file(spec):
    validate_openapi(spec)
    assert render(spec) == (ROOT / "openapi.generated.yaml").read_text()
    assert spec["openapi"] == "3.1.0"
    assert "GameEventV1" in spec["components"]["schemas"]
    assert set(spec["x-source-schemas"]) == set(spec["components"]["schemas"])


def test_same_schema_is_compatible(spec):
    assert compare_specs(spec, copy.deepcopy(spec)) == []


@pytest.mark.parametrize(
    "mutation",
    ["remove-field", "required", "enum", "type", "mate", "remove-route", "auth"],
)
def test_compatibility_gate_rejects_structural_v1_breaks(spec, mutation):
    changed = copy.deepcopy(spec)
    schemas = changed["components"]["schemas"]
    if mutation == "remove-field":
        del schemas["GameSnapshotV1"]["properties"]["fen"]
    elif mutation == "required":
        schemas["CreateGameV1"]["required"].append("human_color")
    elif mutation == "enum":
        schemas["CreateGameV1"]["properties"]["mode"]["enum"].append("rated")
    elif mutation == "type":
        schemas["SubmitMoveV1"]["properties"]["expected_version"]["type"] = "string"
    elif mutation == "mate":
        schemas["AnalysisResultV1"]["allOf"][0]["then"]["properties"]["cp_loss"] = {
            "type": "integer"
        }
    elif mutation == "remove-route":
        del changed["paths"]["/api/v1/games/{id}/moves"]
    else:
        changed["security"] = []
    assert compare_specs(spec, changed)


def test_optional_field_and_new_v2_schema_preserve_v1_structure(spec):
    changed = copy.deepcopy(spec)
    changed["components"]["schemas"]["CreateGameV1"]["properties"]["request_label"] = {
        "type": "string"
    }
    changed["components"]["schemas"]["GameSnapshotV2"] = {"type": "object"}
    assert compare_specs(spec, changed) == []


def test_assembler_rejects_duplicate_operation_ids(tmp_path):
    root = tmp_path / "contracts"
    shutil.copytree(
        ROOT,
        root,
        ignore=shutil.ignore_patterns("node_modules", "generated", "__pycache__"),
    )
    path = root / "common/http.v1.yaml"
    fragment = yaml.safe_load(path.read_text())
    fragment["paths"]["/api/v1/me"]["get"]["operationId"] = "createGame"
    path.write_text(yaml.safe_dump(fragment))
    with pytest.raises(ValueError, match="Duplicate operationId"):
        assemble(root)


def test_check_detects_manual_generated_edit_without_modifying_it(tmp_path):
    root = tmp_path / "contracts"
    shutil.copytree(
        ROOT, root, ignore=shutil.ignore_patterns("node_modules", "__pycache__")
    )
    (root / "node_modules").symlink_to(ROOT / "node_modules", target_is_directory=True)
    generated = Path("backend/app/infra/generated/contracts.py")
    destination = tmp_path / generated
    destination.parent.mkdir(parents=True)
    shutil.copyfile(ROOT.parent / generated, destination)
    artifact = root / "generated/api.d.ts"
    changed = artifact.read_text() + "\n// accidental manual change\n"
    artifact.write_text(changed)
    with pytest.raises(RuntimeError, match="contracts/generated/api.d.ts"):
        generate(root, check=True)
    assert artifact.read_text() == changed
