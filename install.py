"""Adds this pack's garments to an Axcenity character library.

    python -I install.py <library> [--only <text>]... [--remove]

`<library>` is a folder with `catalogue.json` at its root: a project's
`assets/characters/`. Each item's files are checked against `pack.json`
(size and SHA-256), copied to the same path they have under `library/` here,
and listed in the library's catalogue. Items already there are replaced.
`--only` takes the items whose ID contains the text; `--remove` takes the
pack's items out again. Needs Python 3.8 or later, nothing else.
"""

import argparse
import hashlib
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("library", type=pathlib.Path)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    index = args.library / "catalogue.json"
    if not index.is_file():
        sys.exit(f"{args.library} is not a character library: it has no catalogue.json")
    catalogue = json.loads(index.read_text())
    pack = json.loads((HERE / "pack.json").read_text())
    have = {base["id"] for base in catalogue.get("bases", [])}
    items = [i for i in pack["items"] if not args.only or any(o in i["id"] for o in args.only)]
    if not items:
        sys.exit("no item of the pack matches --only")

    if not args.remove:
        for item in items:
            if not set(item["bases"]) <= have:
                sys.exit(f"{item['id']} is made for {item['bases']}, which this library doesn't have")
            for file in item["files"]:
                path = HERE / file["path"]
                if not path.is_file() or path.stat().st_size != file["bytes"] or sha256(path) != file["sha256"]:
                    sys.exit(f"{file['path']} is missing or not the file pack.json lists; get the pack again")

    by_id = {entry["id"]: entry for entry in catalogue["items"]}
    for item in items:
        folder = pathlib.PurePosixPath(item["catalogue"]["manifest"]).parent
        shutil.rmtree(args.library / folder, ignore_errors=True)
        by_id.pop(item["id"], None)
        if not args.remove:
            shutil.copytree(HERE / "library" / folder, args.library / folder)
            by_id[item["id"]] = item["catalogue"]
    catalogue["items"] = sorted(by_id.values(), key=lambda entry: entry["id"])
    with open(index, "w", newline="\n") as f:
        json.dump(catalogue, f, indent=2)
        f.write("\n")
    print(f"{'removed' if args.remove else 'installed'} {len(items)} items; "
          f"the library lists {len(catalogue['items'])}")


if __name__ == "__main__":
    main()
