#!/usr/bin/env python3
"""Install Codex pets from this collection."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import sys
from pathlib import Path
from typing import Any


EXPECTED_ATLAS_SIZE = (1536, 1872)
REQUIRED_PET_KEYS = ("id", "displayName", "description", "spritesheetPath")


class PetError(Exception):
    """A user-facing pet collection error."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_codex_home() -> Path:
    env = os.environ.get("CODEX_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".codex"


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise PetError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PetError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PetError(f"Expected JSON object in {path}")
    return data


def load_collection(root: Path) -> dict[str, Any]:
    data = read_json(root / "collection.json")
    if data.get("schemaVersion") != 1:
        raise PetError("Unsupported collection schemaVersion; expected 1")
    pets = data.get("pets")
    if not isinstance(pets, list):
        raise PetError("collection.json must contain a pets array")
    return data


def pet_entries(collection: dict[str, Any]) -> list[dict[str, Any]]:
    pets = collection["pets"]
    entries: list[dict[str, Any]] = []
    for pet in pets:
        if not isinstance(pet, dict):
            raise PetError("Every pet entry must be an object")
        entries.append(pet)
    return entries


def find_pet(collection: dict[str, Any], pet_id: str) -> dict[str, Any]:
    for pet in pet_entries(collection):
        if pet.get("id") == pet_id:
            return pet
    available = ", ".join(sorted(str(p.get("id")) for p in pet_entries(collection)))
    raise PetError(f"Unknown pet '{pet_id}'. Available pets: {available or 'none'}")


def webp_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None

    offset = 12
    while offset + 8 <= len(data):
        chunk_type = data[offset : offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        payload = offset + 8

        if chunk_type == b"VP8X" and payload + 10 <= len(data):
            width = 1 + int.from_bytes(data[payload + 4 : payload + 7], "little")
            height = 1 + int.from_bytes(data[payload + 7 : payload + 10], "little")
            return width, height
        if chunk_type == b"VP8 " and payload + 10 <= len(data):
            if data[payload + 3 : payload + 6] == b"\x9d\x01\x2a":
                width = struct.unpack_from("<H", data, payload + 6)[0] & 0x3FFF
                height = struct.unpack_from("<H", data, payload + 8)[0] & 0x3FFF
                return width, height
        if chunk_type == b"VP8L" and payload + 5 <= len(data):
            b0, b1, b2, b3 = data[payload + 1 : payload + 5]
            width = 1 + (((b1 & 0x3F) << 8) | b0)
            height = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
            return width, height

        offset = payload + chunk_size + (chunk_size % 2)
    return None


def validate_pet(root: Path, pet: dict[str, Any]) -> tuple[Path, dict[str, Any], Path]:
    pet_id = pet.get("id")
    pet_path_value = pet.get("path")
    if not isinstance(pet_id, str) or not pet_id:
        raise PetError("Pet entry is missing a valid id")
    if not isinstance(pet_path_value, str) or not pet_path_value:
        raise PetError(f"Pet '{pet_id}' is missing a valid path")

    pet_dir = (root / pet_path_value).resolve()
    try:
        pet_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise PetError(f"Pet '{pet_id}' path escapes the repository: {pet_path_value}") from exc

    pet_json = read_json(pet_dir / "pet.json")
    missing = [key for key in REQUIRED_PET_KEYS if not pet_json.get(key)]
    if missing:
        raise PetError(f"Pet '{pet_id}' pet.json missing keys: {', '.join(missing)}")
    if pet_json["id"] != pet_id:
        raise PetError(f"Pet id mismatch: collection has '{pet_id}', pet.json has '{pet_json['id']}'")

    sheet_name = pet_json["spritesheetPath"]
    if not isinstance(sheet_name, str) or Path(sheet_name).name != sheet_name:
        raise PetError(f"Pet '{pet_id}' has an unsafe spritesheetPath")

    sheet_path = pet_dir / sheet_name
    if not sheet_path.exists():
        raise PetError(f"Pet '{pet_id}' is missing spritesheet: {sheet_path}")

    size = webp_size(sheet_path)
    if size is None:
        raise PetError(f"Pet '{pet_id}' spritesheet is not a readable WebP: {sheet_path}")
    if size != EXPECTED_ATLAS_SIZE:
        raise PetError(
            f"Pet '{pet_id}' spritesheet is {size[0]}x{size[1]}; "
            f"expected {EXPECTED_ATLAS_SIZE[0]}x{EXPECTED_ATLAS_SIZE[1]}"
        )

    return pet_dir, pet_json, sheet_path


def command_list(collection: dict[str, Any]) -> int:
    for pet in pet_entries(collection):
        pet_id = pet.get("id", "?")
        display = pet.get("displayName", pet_id)
        desc = pet.get("description", "")
        print(f"{pet_id:16} {display} - {desc}")
    return 0


def command_show(root: Path, collection: dict[str, Any], pet_id: str) -> int:
    pet = find_pet(collection, pet_id)
    pet_dir, pet_json, sheet_path = validate_pet(root, pet)
    print(json.dumps(pet, indent=2, ensure_ascii=False))
    print()
    print(f"pet_json={pet_dir / 'pet.json'}")
    print(f"spritesheet={sheet_path}")
    print(f"install_id={pet_json['id']}")
    return 0


def install_pet(root: Path, codex_home: Path, collection: dict[str, Any], pet_id: str, force: bool) -> None:
    pet = find_pet(collection, pet_id)
    pet_dir, pet_json, sheet_path = validate_pet(root, pet)
    target_dir = codex_home / "pets" / pet_json["id"]

    if target_dir.exists() and not force:
        raise PetError(f"{target_dir} already exists. Re-run with --force to overwrite it.")

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pet_dir / "pet.json", target_dir / "pet.json")
    shutil.copy2(sheet_path, target_dir / sheet_path.name)
    print(f"Installed {pet_json['displayName']} to {target_dir}")


def command_install(root: Path, collection: dict[str, Any], args: argparse.Namespace) -> int:
    install_pet(root, args.codex_home, collection, args.pet_id, args.force)
    return 0


def command_install_all(root: Path, collection: dict[str, Any], args: argparse.Namespace) -> int:
    for pet in pet_entries(collection):
        pet_id = str(pet.get("id"))
        install_pet(root, args.codex_home, collection, pet_id, args.force)
    return 0


def command_remove(codex_home: Path, pet_id: str, force: bool) -> int:
    target_dir = codex_home / "pets" / pet_id
    if not target_dir.exists():
        print(f"{target_dir} is not installed")
        return 0
    if not force:
        raise PetError(f"Refusing to remove {target_dir} without --force")
    shutil.rmtree(target_dir)
    print(f"Removed {target_dir}")
    return 0


def command_validate(root: Path, collection: dict[str, Any]) -> int:
    for pet in pet_entries(collection):
        pet_dir, pet_json, sheet_path = validate_pet(root, pet)
        print(f"ok {pet_json['id']} ({pet_json['displayName']}) - {sheet_path.relative_to(root)}")
        if pet_dir != sheet_path.parent:
            raise AssertionError("unreachable")
    return 0


def command_doctor(root: Path, collection: dict[str, Any], codex_home: Path) -> int:
    print(f"repo_root={root}")
    print(f"codex_home={codex_home}")
    print(f"pets_dir={codex_home / 'pets'}")
    print(f"collection_pets={len(pet_entries(collection))}")
    command_validate(root, collection)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install pets from a Codex pet collection.")
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=default_codex_home(),
        help="Codex home directory. Defaults to CODEX_HOME or ~/.codex.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List available pets.")

    show = subparsers.add_parser("show", help="Show one pet's metadata.")
    show.add_argument("pet_id")

    install = subparsers.add_parser("install", help="Install one pet into Codex.")
    install.add_argument("pet_id")
    install.add_argument("--force", action="store_true", help="Overwrite an existing installed pet.")

    install_all = subparsers.add_parser("install-all", help="Install every pet into Codex.")
    install_all.add_argument("--force", action="store_true", help="Overwrite existing installed pets.")

    remove = subparsers.add_parser("remove", help="Remove one installed pet from Codex.")
    remove.add_argument("pet_id")
    remove.add_argument("--force", action="store_true", help="Confirm removal.")

    subparsers.add_parser("validate", help="Validate every pet in this collection.")
    subparsers.add_parser("doctor", help="Print environment details and validate the collection.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = repo_root()

    try:
        collection = load_collection(root)
        args.codex_home = args.codex_home.expanduser().resolve()

        if args.command == "list":
            return command_list(collection)
        if args.command == "show":
            return command_show(root, collection, args.pet_id)
        if args.command == "install":
            return command_install(root, collection, args)
        if args.command == "install-all":
            return command_install_all(root, collection, args)
        if args.command == "remove":
            return command_remove(args.codex_home, args.pet_id, args.force)
        if args.command == "validate":
            return command_validate(root, collection)
        if args.command == "doctor":
            return command_doctor(root, collection, args.codex_home)

        parser.error(f"Unknown command: {args.command}")
        return 2
    except PetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
