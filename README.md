# Codex Pet Collection

Installable custom pets for Codex.

This repository is a small collection format plus a command-line installer. Each pet is a normal Codex pet package:

```text
pets/<pet-id>/
  pet.json
  spritesheet.webp
```

## Included Pets

| ID | Name | Notes |
| --- | --- | --- |
| `klee` | Klee | Inspired by Klee from Genshin Impact. Hover uses the waving loop through Codex's jumping row. |

## Install

Clone the repository, then run the installer:

```powershell
git clone https://github.com/AcademicAngels/codex-pet-collection.git
cd codex-pet-collection
py scripts/install.py list
py scripts/install.py install klee --force
```

On Windows you can also use the PowerShell wrapper:

```powershell
.\scripts\install.ps1 list
.\scripts\install.ps1 install klee --force
```

The installer copies pets into:

```text
%USERPROFILE%\.codex\pets\<pet-id>
```

If `CODEX_HOME` is set, the installer uses that instead. You can also pass an explicit location:

```powershell
py scripts/install.py --codex-home C:\Users\you\.codex install klee --force
```

After installing or updating a pet, refresh the Codex pet list or restart Codex if the running app still shows cached pet data.

## Commands

```text
list                 List available pets
show <id>            Show metadata for one pet
install <id>         Install one pet
install-all          Install every pet in the collection
remove <id> --force  Remove an installed pet from Codex
validate             Validate collection metadata and spritesheet dimensions
doctor               Print environment details and validate everything
```

## Collection Format

`collection.json` is the index:

```json
{
  "schemaVersion": 1,
  "pets": [
    {
      "id": "klee",
      "displayName": "Klee",
      "path": "pets/klee",
      "spritesheetPath": "spritesheet.webp",
      "preview": "pets/klee/preview/contact-sheet.png",
      "tags": ["genshin", "anime", "custom"]
    }
  ]
}
```

Every pet directory must contain a `pet.json` file and a `1536x1872` WebP spritesheet made from `192x208` cells.

## License Notes

Only add pets and references you have the rights to share. Character-inspired pets may involve third-party IP; keep repository visibility and reuse rules appropriate for your use case.
