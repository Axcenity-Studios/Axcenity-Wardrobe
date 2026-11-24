"""Adds this pack's garments to an Axcenity character library.

    python -I install.py <library> [--only <text>]... [--remove] [--list]
                         [--from <folder or address>]

`<library>` is a folder with `catalogue.json` at its root: a project's
`assets/characters/`. Each item's files are checked against `pack.json`
(size and SHA-256), put at the same path they have under `library/` in the
pack, and listed in the library's catalogue. Items already there are
replaced. `--only` takes the items whose ID contains the text; `--remove`
takes the pack's items out again; `--list` only says what the pack holds.

The garments come from the folder this file is in when the pack is there (a
clone of the repository), and are downloaded otherwise, so this file alone
is enough: only the garments asked for are fetched. `--from` names another
copy of the pack, a folder or an https address.

Needs Python 3.8 or later, nothing else.
"""

import argparse
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ONLINE = "https://raw.githubusercontent.com/Axcenity-Studios/Axcenity-Wardrobe/main"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Pack:
    """A copy of the pack: a folder, or an address its files are fetched from."""

    def __init__(self, source, scratch):
        self.online = source.startswith("https://")
        if not self.online and "://" in source:
            sys.exit(f"{source}: only a folder or an https address")
        self.source = source.rstrip("/")
        self.scratch = pathlib.Path(scratch)

    def file(self, path):
        """Where `path` of the pack is on this computer, fetched first when online."""
        if not self.online:
            return pathlib.Path(self.source) / path
        target = self.scratch / path
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(f"{self.source}/{path}", timeout=60) as answer, open(target, "wb") as f:
                shutil.copyfileobj(answer, f)
        except OSError as error:
            sys.exit(f"could not get {self.source}/{path}: {error}")
        return target

    def checked(self, file):
        """One of an item's files, or an exit when it isn't the file `pack.json` lists."""
        path = self.file(file["path"])
        if not path.is_file() or path.stat().st_size != file["bytes"] or sha256(path) != file["sha256"]:
            sys.exit(f"{file['path']} is missing or not the file pack.json lists; get the pack again")
        return path


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("library", type=pathlib.Path, nargs="?")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--from", dest="source",
                        default=str(HERE) if (HERE / "pack.json").is_file() else ONLINE)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as scratch:
        pack = Pack(args.source, scratch)
        index = json.loads(pack.file("pack.json").read_text())
        items = [i for i in index["items"] if not args.only or any(o in i["id"] for o in args.only)]
        if args.list:
            for item in items:
                print(f"{item['id']:36} {item['label']:24} {item['slot']:10} {item['bytes'] / 1e6:4.0f} MB")
            print(f"{index['name']} {index['version']}, {index['licence']}: {index['credit']}")
            return
        if args.library is None:
            parser.error("name the library to install into")
        catalogue_file = args.library / "catalogue.json"
        if not catalogue_file.is_file():
            sys.exit(f"{args.library} is not a character library: it has no catalogue.json")
        if not items:
            sys.exit("no item of the pack matches --only")
        catalogue = json.loads(catalogue_file.read_text())
        have = {base["id"] for base in catalogue.get("bases", [])}
        by_id = {entry["id"]: entry for entry in catalogue["items"]}

        def write():
            catalogue["items"] = sorted(by_id.values(), key=lambda entry: entry["id"])
            with open(catalogue_file, "w", newline="\n") as f:
                json.dump(catalogue, f, indent=2)
                f.write("\n")

        for item in items:
            folder = args.library / pathlib.PurePosixPath(item["catalogue"]["manifest"]).parent
            if args.remove:
                shutil.rmtree(folder, ignore_errors=True)
                by_id.pop(item["id"], None)
                continue
            if not set(item["bases"]) <= have:
                sys.exit(f"{item['id']} is made for {item['bases']}, which this library doesn't have")
            # Every file is in hand and checked before the library is touched.
            files = [pack.checked(file) for file in item["files"]]
            shutil.rmtree(folder, ignore_errors=True)
            folder.mkdir(parents=True)
            for path in files:
                shutil.copy(path, folder / path.name)
                if pack.online:
                    path.unlink()
            by_id[item["id"]] = item["catalogue"]
            # The catalogue is written after each item, so stopping part way
            # leaves a library that lists what it has.
            write()
            if pack.online:
                print(f"{item['id']}: downloaded ({item['bytes'] / 1e6:.0f} MB)")
        write()
        print(f"{'removed' if args.remove else 'installed'} {len(items)} items; "
              f"the library lists {len(catalogue['items'])}")
        if not args.remove:
            print(f"Credit: {index['credit']}")


if __name__ == "__main__":
    main()
