"""Compile a Windows setup executable from the portable Windows ZIP."""

import argparse
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dist = root / "dist"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", required=True, type=Path, help="Path to Inno Setup's ISCC.exe")
    parser.add_argument("--signtool", type=Path, help="Path to Windows SDK SignTool.exe")
    parser.add_argument("--thumbprint", help="Thumbprint of a code-signing certificate in the Windows certificate store")
    parser.add_argument("--timestamp-url", help="RFC 3161 timestamp service URL")
    args = parser.parse_args()
    signing = (args.signtool, args.thumbprint, args.timestamp_url)
    if any(signing) and not all(signing):
        parser.error("--signtool, --thumbprint and --timestamp-url must be supplied together")
    compiler = args.iscc.resolve(strict=True)
    with TemporaryDirectory(dir=root / "build") as temporary:
        with ZipFile(dist / "BOM-Diff-Tool-Windows-x64.zip") as archive:
            archive.extractall(temporary)
        package = Path(temporary) / "BOM Diff Tool"
        subprocess.run(
            [str(compiler), f"/DPackageDir={package}", f"/O{dist}",
             str(root / "tools" / "BomDiffTool.iss")],
            check=True,
        )
    if all(signing):
        signtool = str(args.signtool.resolve(strict=True))
        installer = str(dist / "BOM-Diff-Tool-Setup-Windows-x64.exe")
        subprocess.run(
            [signtool, "sign", "/sha1", args.thumbprint, "/fd", "SHA256",
             "/tr", args.timestamp_url, "/td", "SHA256", installer],
            check=True,
        )
        subprocess.run([signtool, "verify", "/pa", installer], check=True)


if __name__ == "__main__":
    main()
