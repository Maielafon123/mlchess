"""Conservative v1 change gate; semantic/API meaning still requires human review."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

import yaml

from contracts.validate import ROOT, UniqueKeyLoader

IGNORED = {"description", "title", "examples", "$comment"}


def compare_value(old, new, path: str) -> list[str]:
    if old == new:
        return []
    if isinstance(old, dict) and isinstance(new, dict):
        errors = []
        old_keys = {
            key for key in old if key not in IGNORED and not key.startswith("x-")
        }
        new_keys = {
            key for key in new if key not in IGNORED and not key.startswith("x-")
        }
        if "properties" in old or "properties" in new:
            old_props, new_props = old.get("properties", {}), new.get("properties", {})
            for name, schema in old_props.items():
                if name not in new_props:
                    errors.append(f"{path}/properties/{name}: removed field")
                else:
                    errors.extend(
                        compare_value(
                            schema, new_props[name], f"{path}/properties/{name}"
                        )
                    )
            old_keys.discard("properties")
            new_keys.discard("properties")
        for key in sorted(old_keys | new_keys):
            if key not in old:
                errors.append(f"{path}/{key}: added constraint or required structure")
            elif key not in new:
                errors.append(f"{path}/{key}: removed constraint or required structure")
            elif key in {"required", "enum"}:
                if set(old[key]) != set(new[key]):
                    errors.append(f"{path}/{key}: changed required fields or enum")
            else:
                errors.extend(compare_value(old[key], new[key], f"{path}/{key}"))
        return errors
    if isinstance(old, list) and isinstance(new, list):
        if len(old) != len(new):
            return [f"{path}: changed alternatives or list length"]
        return [
            error
            for index, (left, right) in enumerate(zip(old, new))
            for error in compare_value(left, right, f"{path}/{index}")
        ]
    return [f"{path}: changed type, value, reference or constraint"]


def compare_specs(old: dict, new: dict) -> list[str]:
    errors = []
    for name, schema in old["components"]["schemas"].items():
        target = new["components"]["schemas"].get(name)
        if target is None:
            errors.append(f"schemas/{name}: removed public schema")
        else:
            errors.extend(compare_value(schema, target, f"schemas/{name}"))
    for url, item in old["paths"].items():
        target = new["paths"].get(url)
        if target is None:
            errors.append(f"paths/{url}: removed route")
            continue
        for key, value in item.items():
            if key not in target:
                errors.append(f"paths/{url}/{key}: removed operation or parameters")
            else:
                errors.extend(compare_value(value, target[key], f"paths/{url}/{key}"))
    errors.extend(
        compare_value(old.get("security", []), new.get("security", []), "security")
    )
    errors.extend(
        compare_value(
            old["components"].get("securitySchemes", {}),
            new["components"].get("securitySchemes", {}),
            "securitySchemes",
        )
    )
    return errors


def check_against_git(base_ref: str, root: Path = ROOT) -> None:
    if re.fullmatch(r"0{40}", base_ref):
        print("Initial repository push: public contracts still require review.")
        return
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", base_ref):
        raise ValueError("Expected a commit SHA or a simple Git ref")
    repo = root.parent
    subprocess.run(
        ["git", "rev-parse", "--verify", base_ref],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    relative = "contracts/openapi.generated.yaml"
    present = subprocess.check_output(
        ["git", "ls-tree", "--name-only", base_ref, "--", relative], cwd=repo, text=True
    ).strip()
    if not present:
        print(
            "Base has no generated API: initial contract review is required; no accepted baseline claimed."
        )
        return
    raw = subprocess.check_output(
        ["git", "show", f"{base_ref}:{relative}"], cwd=repo, text=True
    )
    old = yaml.load(raw, Loader=UniqueKeyLoader)
    new = yaml.load(
        (root / "openapi.generated.yaml").read_text(encoding="utf-8"),
        Loader=UniqueKeyLoader,
    )
    errors = compare_specs(old, new)
    if errors:
        raise ValueError(
            "Potential breaking v1 changes:\n"
            + "\n".join(errors)
            + "\nPreserve v1 and introduce a reviewed v2 contract."
        )
    print("No structural breaking change against " + base_ref)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", default="main")
    args = parser.parse_args()
    check_against_git(args.base_ref)
