"""Build and verify the approved v1.0.13 browser/full packages offline.

Usage: python package_release.py BASELINE_ZIP RELEASE_SOURCE OUTPUT_DIR SCRATCH_DIR
The supplied release source must already contain the final docs and test evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


BASELINE_SHA256 = "f2bb3e99f3185578e5e9a56e45ef6fa086b602f423025e379a5f3f6d1cb2bb50"
PREFIX = "teals-sunday-pickem-main"
MODIFIED = {
    "app.py", "config.py", "weekly_ui.py",
    "tests/test_gate2_edit_backup_polish.py", "tests/test_v103_launch_polish.py",
    "tests/test_v108_hotfix81_pulse_placement.py", "tests/test_v110_render_reuse.py",
}
NEW_TEST_FILES = {"tests/test_v113_lineup_actions.py", "tests/lineup_ui_fixture.py"}
CHECKSUM_FILE = "SHA256SUMS_v1.0.13.txt"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_files(root):
    files = {}
    for path in sorted(root.rglob("*")):
        if {"__pycache__", ".pytest_cache", ".git"}.intersection(path.parts):
            continue
        if path.is_file():
            assert not path.is_symlink(), path
            assert path.suffix not in {".pyc", ".pyo"}, path
            assert path.name not in {".env", "secrets.toml"}, path
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def assert_test_result(evidence, stem, count):
    tree = ET.parse(evidence / f"{stem}.xml")
    suites = list(tree.getroot().iter("testsuite"))
    assert sum(int(s.attrib["tests"]) for s in suites) == count
    for field in ("errors", "failures", "skipped"):
        assert sum(int(s.attrib.get(field, 0)) for s in suites) == 0, (stem, field)
    marker = json.loads((evidence / f"{stem}.log").read_text().splitlines()[-1])
    assert marker["pytest_exit"] == marker["blocked_network_attempts"] == 0
    return {"tests_passed": count, "python": marker["python"], "blocked_network_attempts": 0}


def write_zip(path, files):
    with ZipFile(path, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert {i.filename: archive.read(i.filename) for i in archive.infolist()} == files


def main():
    baseline_zip, release, output, scratch = map(lambda x: Path(x).resolve(), sys.argv[1:])
    assert sha(baseline_zip.read_bytes()) == BASELINE_SHA256
    with ZipFile(baseline_zip) as archive:
        baseline = {i.filename.removeprefix(PREFIX + "/"): archive.read(i.filename)
                    for i in archive.infolist() if not i.is_dir()}
    assert len(baseline) == 302
    assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in baseline)
    current = source_files(release)
    assert set(baseline) <= set(current), "Original file deletion"
    assert {p for p in baseline if baseline[p] != current[p]} == MODIFIED
    assert current["app.py"].split(b"\npage_config()\n", 1)[1] == baseline["app.py"].split(b"\npage_config()\n", 1)[1]
    checksums = "".join(f"{sha(data)}  {name}\n" for name, data in current.items() if name != CHECKSUM_FILE)
    (release / CHECKSUM_FILE).write_text(checksums)
    current = source_files(release)
    added = set(current) - set(baseline)
    assert {p for p in added if p.startswith("tests/")} == NEW_TEST_FILES
    evidence = release / "performance_evidence/v1_0_13"
    tests = {stem: assert_test_result(evidence, stem, count) for stem, count in (
        ("release_312", 479), ("release_313", 479), ("rollback_313", 446))}
    comparison = json.loads((evidence / "comparison.json").read_text())
    assert comparison["status"] == "PASS" and comparison["compared_scenario_pairs"] == 185
    scratch.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    upload = {p: current[p] for p in sorted(MODIFIED | added)}
    assert len(upload) <= 100 and max(map(len, upload.values())) < 25 * 1024 * 1024
    full_path = output / "Teals_Sunday_Pickem_v1.0.13_FULL_CURRENT_APP.zip"
    small_path = output / "Teals_Sunday_Pickem_v1.0.13_GITHUB_BROWSER_UPLOAD.zip"
    with tempfile.TemporaryDirectory(prefix="verify-v113-", dir=scratch) as temp_name:
        temp = Path(temp_name)
        py_sources = [p for p in current if p.endswith(".py")]
        compiled = temp / "compiled"
        compiled.mkdir()
        for index, name in enumerate(py_sources):
            py_compile.compile(str(release / name), cfile=str(compiled / f"{index}.pyc"), doraise=True)
        guard = subprocess.run([sys.executable, "release_guard.py"], cwd=release, capture_output=True, text=True)
        assert guard.returncode == 0, guard.stdout + guard.stderr
        write_zip(full_path, {PREFIX + "/" + p: data for p, data in current.items()})
        # Build the small payload first; the verification record is added only
        # after checking actual extracted bytes and is outside the upload tree.
        small_files = {"START_HERE.md": current["START_HERE_v1.0.13.md"]}
        small_files.update({"UPLOAD_TO_GITHUB/" + p: data for p, data in upload.items()})
        small_files.update({"ROLLBACK_ONLY/" + p: baseline[p] for p in sorted(MODIFIED)})
        write_zip(small_path, small_files)
        with ZipFile(full_path) as archive:
            archive.extractall(temp / "full")
        with ZipFile(baseline_zip) as archive:
            archive.extractall(temp / "overlay")
        with ZipFile(small_path) as archive:
            archive.extractall(temp / "small")
        full_root = temp / "full" / PREFIX
        overlay_root = temp / "overlay" / PREFIX
        shutil.copytree(temp / "small/UPLOAD_TO_GITHUB", overlay_root, dirs_exist_ok=True)
        assert source_files(full_root) == source_files(overlay_root) == current
        rollback_root = temp / "rollback"
        shutil.copytree(full_root, rollback_root)
        shutil.copytree(temp / "small/ROLLBACK_ONLY", rollback_root, dirs_exist_ok=True)
        for name in NEW_TEST_FILES:
            (rollback_root / name).unlink()
        rollback = source_files(rollback_root)
        assert all(rollback[p] == data for p, data in baseline.items())
        assert not any(p.startswith("tests/") for p in set(rollback) - set(baseline))
        verification = {
            "status": "PASS", "version": "1.0.13", "build": "1.0.13-performance4",
            "baseline_zip_sha256": BASELINE_SHA256, "original_files": len(baseline),
            "full_release_files": len(current), "modified_original_files": sorted(MODIFIED),
            "added_files": sorted(added), "deleted_original_files": [],
            "upload_file_count": len(upload), "largest_upload_file_bytes": max(map(len, upload.values())),
            "python_files_compiled": len(py_sources), "release_guard": guard.stdout.strip(),
            "app_body_after_page_config": "byte-identical to v1.0.12",
            "overlay": "all file names and bytes identical to full release",
            "manual_rollback": "all 302 original files byte-identical; two new test files deleted",
            "rollback_allowed_extras": sorted(set(rollback) - set(baseline)),
            "regression_tests": tests, "compared_scenario_pairs": 185,
            "upload_sha256": {name: sha(data) for name, data in upload.items()},
        }
        small_files["PACKAGING_VERIFICATION.json"] = (json.dumps(verification, indent=2) + "\n").encode()
        write_zip(small_path, small_files)
        # Verify the final archive payload after adding the outside-the-upload report.
        with ZipFile(small_path) as archive:
            final_upload = {i.filename.removeprefix("UPLOAD_TO_GITHUB/"): archive.read(i.filename)
                            for i in archive.infolist() if i.filename.startswith("UPLOAD_TO_GITHUB/")}
        assert {**baseline, **final_upload} == current
    verification["artifacts"] = {
        p.name: {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
        for p in (small_path, full_path)
    }
    (output / "Pickem_v1.0.13_Package_Verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    print(json.dumps({k: verification[k] for k in (
        "status", "original_files", "full_release_files", "upload_file_count", "python_files_compiled", "artifacts")}, indent=2))


if __name__ == "__main__":
    main()
