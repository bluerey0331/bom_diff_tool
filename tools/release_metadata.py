"""Record the inputs, test results and hashes for a Windows release build."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ASSETS = ("BOM-Diff-Tool-Windows-x64.zip", "BOM-Diff-Tool-Setup-Windows-x64.exe")
SOURCE_ARCHIVE = "BOM-Diff-Tool-Build-Source.zip"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, encoding="utf-8").strip()


def test_counts(path):
    suites = ET.parse(path).getroot()
    counts = {key: sum(int(suite.get(key, 0)) for suite in suites.iter("testsuite"))
              for key in ("tests", "failures", "errors", "skipped")}
    if counts["failures"] or counts["errors"] or not counts["tests"]:
        raise SystemExit("A passing test report is required.")
    return counts


def authenticode(artifact):
    return subprocess.check_output(
        ["pwsh.exe", "-NoProfile", "-Command",
         "(Get-AuthenticodeSignature -LiteralPath $env:BOM_RELEASE_EXE).Status.ToString()"],
        encoding="ascii", env={**os.environ, "BOM_RELEASE_EXE": str(artifact)},
    ).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--installer-verification", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    dist = root / "dist"
    files = [root / name for name in
             ("main.py", "prepare.py", "README.md", "README_JP.md", "CHANGELOG.md",
              "requirements.txt", "config.ini.example", "LICENSE",
              "sample_old.xlsx", "sample_new.xlsx", "samples/demo_old_bom.xlsx",
              "samples/demo_new_bom.xlsx", "tools/BomDiffTool.iss", "tools/build_windows.py",
              "tools/build_installer.py", "tools/release_metadata.py", "tools/verify_installer.ps1",
              ".github/workflows/windows-download.yml")]
    files.extend(sorted((root / "src").glob("*.py")))
    files.extend(sorted((root / "tests").glob("*.py")))
    audit = None
    if args.audit:
        report = json.loads(args.audit.read_text(encoding="utf-8-sig"))
        audit = {
            "vulnerabilities": sum(len(dep.get("vulns", [])) for dep in report["dependencies"]),
            "skipped_packages": [dep["name"] for dep in report["dependencies"] if "skip_reason" in dep],
        }
    sources = {path.relative_to(root).as_posix(): path for path in files}
    with ZipFile(dist / SOURCE_ARCHIVE, "w", compression=ZIP_DEFLATED) as archive:
        for name, path in sources.items():
            archive.write(path, name)
    hashes = {name: digest(dist / name) for name in (*ASSETS, SOURCE_ARCHIVE)}
    installer_verification = None
    if args.installer_verification:
        installer_verification = json.loads(args.installer_verification.read_text(encoding="utf-8-sig"))
        if installer_verification.get("installer_sha256") != hashes[ASSETS[1]]:
            raise SystemExit("The installer verification belongs to a different build.")
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": git(root, "rev-parse", "HEAD"),
        "working_tree_clean": not git(root, "status", "--porcelain"),
        "source_sha256": {name: digest(path) for name, path in sources.items()},
        "python": platform.python_version(),
        "build_platform": platform.platform(),
        "dependencies": json.loads(subprocess.check_output(
            [sys.executable, "-m", "pip", "list", "--format=json"], encoding="utf-8")),
        "tests": test_counts(args.tests),
        "dependency_audit": audit,
        "installer_authenticode": authenticode(dist / ASSETS[1]),
        "installer_verification": installer_verification,
        "artifact_sha256": hashes,
    }
    (dist / "release-metadata.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dist / "SHA256SUMS.txt").write_text(
        "".join(f"{value}  {name}\n" for name, value in hashes.items()), encoding="ascii")


if __name__ == "__main__":
    main()
