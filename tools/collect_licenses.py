"""Write the licence texts of everything the PyInstaller build ships into dist\\WallSwap.

Run by build.ps1 after PyInstaller:  uv run python tools/collect_licenses.py dist\\WallSwap
Output: LICENSE.txt (WallSwap's own) and THIRD_PARTY_LICENSES.txt (Python and the libraries it bundles, Tcl/Tk, and
every Python package the app depends on at runtime, with the licence files from each package's metadata).
"""
import re
import shutil
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENSE_FILE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.IGNORECASE)


def runtime_packages() -> list[metadata.Distribution]:
    """The project's runtime dependencies and everything they require (markers for this platform only)."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    todo = [re.split(r"[<>=!~;\[ ]", dep, maxsplit=1)[0] for dep in project["dependencies"]]
    todo.append("setuptools")  # PyInstaller bundles it for pkg_resources
    seen: dict[str, metadata.Distribution] = {}
    while todo:
        name = todo.pop().lower().replace("_", "-")
        if name in seen:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue  # a platform-only dependency that isn't installed here
        seen[name] = dist
        for req in dist.requires or []:
            spec, _, marker = req.partition(";")
            if "extra" in marker:
                continue
            if marker.strip():
                from packaging.markers import Marker
                if not Marker(marker.strip()).evaluate():
                    continue
            todo.append(re.split(r"[<>=!~\[ (]", spec.strip(), maxsplit=1)[0])
    return sorted(seen.values(), key=lambda d: d.metadata["Name"].lower())


def licence_texts(dist: metadata.Distribution) -> list[tuple[str, str]]:
    texts = []
    for file in dist.files or []:
        if ".dist-info" in str(file) and LICENSE_FILE.search(file.name):
            try:
                texts.append((file.name, Path(file.locate()).read_text(encoding="utf-8", errors="replace")))
            except OSError:
                pass
    return texts


def section(title: str, body: str) -> str:
    return f"{'=' * 78}\n{title}\n{'=' * 78}\n\n{body.strip()}\n\n"


def main(out_dir: Path) -> None:
    shutil.copyfile(ROOT / "LICENSE", out_dir / "LICENSE.txt")
    parts = [
        "WallSwap bundles the software below. Each part keeps its own licence; the texts follow.\n"
        "Source for every Python package is on PyPI (https://pypi.org/project/<name>/). pystray is LGPL-3.0: its\n"
        "source is at https://github.com/moses-palmer/pystray, and you may replace the bundled copy with your own\n"
        "build of it.\n\n"
    ]
    base = Path(sys.base_prefix)
    parts.append(section("Python (includes the licences of OpenSSL, libffi, zlib, bzip2, xz and others it ships)",
                         (base / "LICENSE.txt").read_text(encoding="utf-8", errors="replace")))
    # Tcl and Tk share one licence; Python's Windows build keeps a copy in tk8.6 (and sometimes tcl8.6)
    terms = next((p for p in (base / "tcl" / "tcl8.6" / "license.terms", base / "tcl" / "tk8.6" / "license.terms")
                  if p.exists()), None)
    if terms:
        parts.append(section("Tcl/Tk 8.6", terms.read_text(encoding="utf-8", errors="replace")))
    missing = []
    for dist in runtime_packages():
        meta = dist.metadata
        title = f"{meta['Name']} {dist.version} — {meta.get('License-Expression') or meta.get('License') or ''}".strip()
        texts = licence_texts(dist)
        if not texts:
            missing.append(meta["Name"])
            # The winrt-* wheels ship no licence file; they come from the pywinrt project (MIT)
            home = ("https://github.com/pywinrt/pywinrt/blob/main/LICENSE" if meta["Name"].lower().startswith("winrt")
                    else f"https://pypi.org/project/{meta['Name']}/{dist.version}/")
            texts = [("", f"The package ships no licence file. Licence text: {home}")]
        parts.append(section(title.splitlines()[0][:120], "\n\n".join(f"--- {n} ---\n{t}" if n else t for n, t in texts)))
    (out_dir / "THIRD_PARTY_LICENSES.txt").write_text("".join(parts), encoding="utf-8")
    print(f"Wrote {out_dir / 'THIRD_PARTY_LICENSES.txt'}" + (f" (no licence file in: {', '.join(missing)})" if missing else ""))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
