"""One-shot, branch-scoped materialization of reviewed source files.

Transport is compressed UTF-8 JSON in ordinary Git blobs, not an executable archive.
Every blob and every resulting source file is hash checked. Training/results are not
modified. This helper is deleted before the tested source commit is made.
"""
from __future__ import annotations
import base64
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import time
import urllib.request

REPO = "homulillew/ESR-Tra"
BRANCH = "refactor/esr-state-2.1"
BASE = "6ee9c4a264cd80a50d8a15511c8ed80b39c763b6"
PAYLOAD_SHA = "c11cf2e93590a58940f14cc45ce49f0894264ca1446dd020aa01c2317d790e48"
BLOBS = [
 "773bbe9d24a97c523a1092d80a3a76d266103ab2",
 "0f4351e6908e59c0418a2433bc90f06daed70cfb",
 "d22580cfa2980e67276bdc51d8a4f69788f78353",
 "ca6642d5e397621b5bb29ef9ed7742164ad9450d",
 "d1f59212c743b2a331126d30a4cae43bfde8f975",
 "88778fcc954724cc8db9a7a85171e766c3eebabc",
 "251ef0915d0f481c6dc22a6da40df161fe0a7c59",
 "030ce1ac5f002b4a27dfb166e3e42b0ab18ae9c5",
 "a2b20f87db51bea70ed40261808c48b7972d51ec",
 "aa0a02c87366c17a67c31f7e640eb4d47c67a91a",
 "d484001fbeee063ddb6469c08f433548f2f58e74",
 "7ab98f04bd9c284f2cd738ea59080f3861a5542a",
]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def allowed(name: str) -> bool:
    p = PurePosixPath(name)
    return (not p.is_absolute() and ".." not in p.parts and "\\" not in name and
            (name in {"README.md", "pyproject.toml", "tests/__init__.py", ".github/workflows/harness-v2.yml"}
             or name.startswith(("src/esr_harness/", "tests/harness_v2/", "tests/harness_v21/", "docs/harness/", "docs/research/state_21/"))))


def get_blob(sha: str) -> bytes:
    url = f"https://api.github.com/repos/{REPO}/git/blobs/{sha}"
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                row = json.load(response)
            if row.get("encoding") != "base64":
                raise ValueError("Unexpected Git blob encoding")
            data = base64.b64decode(row["content"])
            actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if actual != sha:
                raise ValueError("Transport blob hash mismatch")
            return data
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise AssertionError("unreachable")


def main() -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPO or os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise RuntimeError("This importer is restricted to the requested new branch")
    subprocess.run(["git", "merge-base", "--is-ancestor", BASE, "HEAD"], check=True)
    if Path("src/esr_harness/v2").exists():
        raise RuntimeError("Refusing to overwrite an existing frozen v2 package")
    payload = b"".join(get_blob(sha) for sha in BLOBS)
    if len(payload) != 91712 or hashlib.sha256(payload).hexdigest() != PAYLOAD_SHA:
        raise ValueError("Combined payload hash mismatch")
    decoded = json.loads(lzma.decompress(payload))
    files, expected = decoded["files"], decoded["sha256"]
    if len(files) != 41 or len(expected) != 59:
        raise ValueError("Unexpected source manifest")
    for name in set(files) | set(expected):
        if not allowed(name):
            raise ValueError("Unapproved write path: " + name)
        p = Path(name)
        if p.is_symlink() or any(parent.is_symlink() for parent in p.parents):
            raise ValueError("Symlink destination rejected")
    workflow = ".github/workflows/harness-v2.yml"
    if Path(workflow).read_bytes() != files[workflow].encode("utf-8"):
        raise ValueError("CI workflow must first be installed through the connector")

    frozen = Path("src/esr_harness/v2")
    frozen.mkdir()
    for path in Path("src/esr_harness").glob("*.py"):
        shutil.copyfile(path, frozen / path.name)

    for path in Path("tests/harness_v2").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        text = text.replace("esr_harness.", "esr_harness.v2.")
        text = text.replace("from esr_harness import cli", "from esr_harness.v2 import cli")
        text = text.replace("from conftest import", "from .conftest import")
        path.write_text(text, encoding="utf-8")
    Path("tests/__init__.py").write_text("", encoding="utf-8")
    Path("tests/harness_v2/__init__.py").write_text("", encoding="utf-8")

    archives = []
    for original in ["docs/harness/DESIGN.md", "docs/harness/RUNBOOK.md", "docs/harness/VALIDATION.md", "README.md"]:
        source = Path(original)
        if not source.is_file():
            raise ValueError("Missing expected v2 documentation: " + original)
        destination = Path("docs/harness/archive") / (source.stem + "_v2.md")
        if destination.exists():
            raise ValueError("Refusing to overwrite documentation archive")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        archives.append(str(destination))

    for name, text in files.items():
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    for name, sha in expected.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != sha:
            raise ValueError("Materialized file mismatch: " + name)
    expected.update({name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in archives})
    Path("/tmp/state21-expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    # The workflow itself is removed later using the user's connector, not a CI token.
    Path(".state21-import.py").unlink()
    staged = sorted((set(expected) - {workflow}) | {".state21-import.py"})
    Path("/tmp/state21-staged-paths.json").write_text(json.dumps(staged, ensure_ascii=False), encoding="utf-8")
    for name in git("diff", "--name-only").splitlines():
        if name != ".state21-import.py" and not allowed(name):
            raise ValueError("Unexpected changed path: " + name)
    print(f"Verified {len(expected)} source/document paths; legacy source and v2 docs frozen. No model experiments run.")


if __name__ == "__main__":
    main()
