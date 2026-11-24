"""Builds this pack from a character library that holds the fitted items.

    python -I tools/build_pack.py --library <library> [--outfits <folder>]

`<library>` is an Axcenity character library (a folder with `catalogue.json`)
in which the garments have been imported, for example by the engine's
`assets/characters/realistic/clothing/generated/import_generated.py`.

Copies every item whose ID starts with `items_with_prefix` (see
`pack.config.json` beside this file) into `library/`, at the same path it has
in the source library, leaving out the ones under `held_back`. Copies the
character files in `--outfits` that wear only items this pack or the engine
has into `outfits/`. Then writes `pack.json`, the index of the pack, and
`GALLERY.md`, the same list with pictures.

An item whose manifest names another author or licence than the pack's is an
error: nothing is published under a licence it wasn't recorded with.
"""

import argparse
import datetime
import hashlib
import json
import pathlib
import shutil
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
PACK_FORMAT = 1


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def glb_counts(path):
    """A `.glb`'s triangle count and how many shapes (morph targets) it carries."""
    with open(path, "rb") as f:
        f.read(12)
        length, _ = struct.unpack("<II", f.read(8))
        gltf = json.loads(f.read(length))
    triangles, shapes = 0, 0
    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if "indices" in primitive:
                triangles += gltf["accessors"][primitive["indices"]]["count"] // 3
            shapes = max(shapes, len(primitive.get("targets", [])))
    return triangles, shapes


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--library", required=True, type=pathlib.Path)
    parser.add_argument("--outfits", type=pathlib.Path)
    args = parser.parse_args()
    config = json.loads((HERE / "pack.config.json").read_text())
    catalogue = json.loads((args.library / "catalogue.json").read_text())
    held_back = config.get("held_back", {})

    target = ROOT / "library"
    shutil.rmtree(target, ignore_errors=True)
    items, bases = [], set()
    for entry in sorted(catalogue["items"], key=lambda e: e["id"]):
        if not entry["id"].startswith(config["items_with_prefix"]) or entry["id"] in held_back:
            continue
        manifest_path = args.library / entry["manifest"]
        manifest = json.loads(manifest_path.read_text())
        source = manifest.get("source", {})
        if (source.get("author"), source.get("licence")) != (config["author"], config["licence"]):
            sys.exit(f"{entry['id']}: recorded as {source}, not {config['author']} / {config['licence']}")
        folder = pathlib.PurePosixPath(entry["manifest"]).parent
        shutil.copytree(args.library / folder, target / folder)
        files = []
        for path in sorted((target / folder).iterdir()):
            files.append({"path": f"library/{folder}/{path.name}", "bytes": path.stat().st_size,
                          "sha256": sha256(path)})
        triangles, shapes = glb_counts(target / folder / manifest["model"]["file"])
        bases.update(manifest["bases"])
        name = entry["id"].split("/")[-1]
        item = {"id": entry["id"], "label": manifest["label"], "kind": manifest["kind"],
                "slot": manifest["slot"], "layer": manifest.get("layer", 0),
                "quality": manifest.get("quality", "draft"), "bases": manifest["bases"],
                "triangles": triangles, "shapes": shapes,
                "bytes": sum(f["bytes"] for f in files),
                "preview": f"previews/{name}.png", "catalogue": entry, "files": files}
        items.append(item)

    outfits = []
    if args.outfits:
        shutil.rmtree(ROOT / "outfits", ignore_errors=True)
        (ROOT / "outfits").mkdir()
        ours = {i["id"] for i in items}
        others = {e["id"] for e in catalogue["items"] if not e["id"].startswith(config["items_with_prefix"])}
        for path in sorted(args.outfits.glob("*.character.json")):
            character = json.loads(path.read_text())
            worn = [i["id"] for i in character["items"]]
            if not all(i in ours or i in others for i in worn):
                continue
            shutil.copy(path, ROOT / "outfits" / path.name)
            outfits.append({"name": character["name"], "file": f"outfits/{path.name}",
                            "base": character["base"], "items": worn})

    pack = {"format": "axcenity-character-pack", "format_version": PACK_FORMAT,
            "id": config["id"], "name": config["name"], "version": config["version"],
            "date": datetime.date.today().isoformat(),
            "author": config["author"], "licence": config["licence"], "credit": config["credit"],
            "repository": config["repository"], "files_at": config["files_at"],
            "bases": sorted(bases), "bytes": sum(i["bytes"] for i in items),
            "items": items, "outfits": outfits,
            "held_back": [{"id": k, "why": v} for k, v in sorted(held_back.items())]}
    (ROOT / "pack.json").write_text(json.dumps(pack, indent=2) + "\n")

    slots = {}
    for item in items:
        slots.setdefault(item["slot"], []).append(item)
    lines = [f"# {config['name']} {config['version']}: the garments", "",
             "Written by `tools/build_pack.py`. Each garment alone, from the front "
             "(`tools/render_previews.py`).", ""]
    for slot in sorted(slots):
        lines += [f"## {slot.replace('_', ' ').capitalize()}", "", "| | Garment | ID | Triangles | Size |",
                  "|---|---|---|---|---|"]
        for item in slots[slot]:
            lines.append(f"| <img src=\"{item['preview']}\" width=\"128\" alt=\"\"> | {item['label']} | "
                         f"`{item['id']}` | {item['triangles']:,} | {item['bytes'] / 1e6:.0f} MB |")
        lines.append("")
    (ROOT / "GALLERY.md").write_text("\n".join(lines))
    print(f"{len(items)} items, {len(outfits)} outfits, {pack['bytes'] / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
