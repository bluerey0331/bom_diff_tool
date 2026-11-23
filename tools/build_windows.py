"""Build the portable Windows x64 distribution from the repository root."""

import platform
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path


def main() -> None:
    if sys.platform != "win32" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        raise SystemExit("Build this distribution with 64-bit x86 Python on Windows.")

    root = Path(__file__).resolve().parents[1]
    dist = root / "dist"
    name = "BOM Diff Tool"
    dist.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=dist) as directory:
        staging = Path(directory)
        subprocess.run(
            [
                sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                "--onedir", "--windowed", "--noupx", "--name", name,
                "--distpath", str(staging), "--workpath", str(root / "build" / "pyinstaller"),
                "--specpath", str(root / "build"), "main.py",
            ],
            cwd=root,
            check=True,
        )
        package = staging / name
        shutil.copy2(package / f"{name}.exe", package / f"{name} (English).exe")
        for filename in ("LICENSE", "config.ini.example"):
            shutil.copy2(root / filename, package / filename)
        samples = package / "samples"
        samples.mkdir(exist_ok=True)
        for filename in ("sample_old.xlsx", "sample_new.xlsx"):
            shutil.copy2(root / filename, samples / filename)
        for revision in ("old", "new"):
            filename = f"demo_{revision}_bom.xlsx"
            shutil.copy2(root / "samples" / filename, samples / filename)
        archive = shutil.make_archive(str(dist / "BOM-Diff-Tool-Windows-x64"), "zip", staging, name)
        print(archive)


if __name__ == "__main__":
    main()
