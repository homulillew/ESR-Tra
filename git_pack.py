#!/usr/bin/env python3
"""git_pack.py — 按 /data1/Git规则.md 生成离线 .b64 目录型发布包。

支持：
  python git_pack.py full V5               # Full 全量包  release/full/V5/
  python git_pack.py diff V4 V5            # Diff 增量包  release/diff/V4_to_V5/
  python git_pack.py verify <release路径>  # 校验 manifest/Base64/SHA256/缺失

规则要点（见 Git规则.md）：
  - 只从 Git tag/commit 读取文件，绝不混入工作区未提交修改。
  - 每个文件：原始路径不变，文件名末尾追加 .b64，内容为【单行】Base64。
  - SHA256 针对【原始文件内容】计算（非 .b64）。
  - Diff：A/M/R新路径 从 TO 版本读完整文件；D/R旧路径 记入 deleted.txt；R 不保留 rename 语义。
  - manifest.json 记录 type/from/to/commit/files{sha256, mode}/deleted。
  - 仅包含 git tracked files。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def git(args: list[str], cwd: Path) -> str:
    """统一带 -c core.quotepath=false，保证中文/特殊文件名返回原始 UTF-8 而非引号+八进制。"""
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd,
                          capture_output=True, text=True, check=True).stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_file_bytes(repo: Path, ref: str, path: str) -> bytes:
    """用 git show <ref>:<path> 读取指定版本的文件原始内容。"""
    out = subprocess.run(["git", "-c", "core.quotepath=false", "show", f"{ref}:{path}"], cwd=repo,
                         capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"git show {ref}:{path} 失败: {out.stderr.decode('utf-8','replace')[:200]}")
    return out.stdout


def get_mode(repo: Path, ref: str, path: str) -> str:
    """从 ls-tree 读取文件 mode (100644/100755)，符号链 120000。"""
    try:
        line = git(["ls-tree", ref, "--", path], repo).strip()
    except Exception:
        return ""
    if not line:
        return ""
    # 格式: <mode> <type> <hash>\t<path>
    return line.split()[0] if line.split() else ""


def write_b64(dst_dir: Path, rel: str, data: bytes, mode: str) -> dict:
    """写 {原路径}.b64 单行 Base64；返回 manifest 的 files 项。"""
    out_path = dst_dir / f"{rel}.b64"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    b64 = base64.b64encode(data).decode("ascii")  # 单行，无换行
    out_path.write_text(b64, encoding="ascii")
    entry: dict = {"sha256": sha256_bytes(data)}
    if mode in ("100755", "120000"):
        entry["mode"] = mode
    return entry


def resolve_commit(repo: Path, ref: str) -> str:
    """返回 ref 指向的真实 commit hash（剥掉 annotated tag 对象层）。"""
    return git(["rev-parse", f"{ref}^{{}}"], repo).strip()


def make_full(repo: Path, version: str, out_root: Path) -> Path:
    git(["rev-parse", "--verify", version, "--"], repo)
    commit = resolve_commit(repo, version)
    tracked = git(["ls-tree", "-r", "--name-only", version], repo).splitlines()
    pkg = out_root / "full" / version
    files_dir = pkg / "files"
    files: dict[str, dict] = {}
    for rel in tracked:
        data = read_file_bytes(repo, version, rel)
        mode = get_mode(repo, version, rel)
        files[rel] = write_b64(files_dir, rel, data, mode)
    manifest = {
        "type": "full",
        "version": version,
        "commit": commit,
        "files": files,
        "deleted": [],
    }
    (pkg / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return pkg


def make_diff(repo: Path, from_ref: str, to_ref: str, out_root: Path) -> Path:
    git(["rev-parse", "--verify", from_ref, "--"], repo)
    git(["rev-parse", "--verify", to_ref, "--"], repo)
    to_commit = resolve_commit(repo, to_ref)
    # diff --name-status -M from to
    raw = git(["diff", "--name-status", "-M", from_ref, to_ref], repo)
    deleted: list[str] = []
    pkg = out_root / "diff" / f"{from_ref}_to_{to_ref}"
    files_dir = pkg / "files"
    files: dict[str, dict] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0][0]
        if status in ("A", "M", "C"):
            rel = parts[1]
            mode = get_mode(repo, to_ref, rel)
            data = read_file_bytes(repo, to_ref, rel)
            files[rel] = write_b64(files_dir, rel, data, mode)
        elif status == "D":
            deleted.append(parts[1])
        elif status == "R":
            # 旧路径删除 + 新路径新增
            _ = parts[1]
            new_rel = parts[2]
            deleted.append(parts[1])  # 注意: R 格式 2 个路径, 旧在前
            mode = get_mode(repo, to_ref, new_rel)
            data = read_file_bytes(repo, to_ref, new_rel)
            files[new_rel] = write_b64(files_dir, new_rel, data, mode)
        else:
            raise RuntimeError(f"未知 diff status: {status} {parts}")
    # deleted.txt
    if deleted:
        (pkg / "deleted.txt").write_text("\n".join(deleted) + "\n", encoding="utf-8")
    else:
        (pkg / "deleted.txt").write_text("", encoding="utf-8")
    manifest = {
        "type": "diff",
        "from": from_ref,
        "to": to_ref,
        "commit": to_commit,
        "files": files,
        "deleted": deleted,
    }
    (pkg / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return pkg


def verify(pkg: Path) -> int:
    """校验 manifest / Base64 可解码 / SHA256 / 文件缺失。校验原始内容 SHA256。"""
    manifest = json.loads((pkg / "manifest.json").read_text(encoding="utf-8"))
    files_dir = pkg / "files"
    errors = 0
    n = len(manifest["files"])
    for i, (rel, entry) in enumerate(manifest["files"].items(), 1):
        b64_path = files_dir / f"{rel}.b64"
        if not b64_path.exists():
            print(f"  [缺失] {rel}.b64")
            errors += 1
            continue
        try:
            raw = base64.b64decode(b64_path.read_text(encoding="ascii").strip())
        except Exception as exc:
            print(f"  [b64错误] {rel}: {exc}")
            errors += 1
            continue
        h = sha256_bytes(raw)
        if h != entry.get("sha256"):
            print(f"  [SHA256不匹配] {rel}")
            errors += 1
    print(f"manifest files={n}, deleted={len(manifest.get('deleted', []))}")
    print("✓ 未发现缺失/损坏" if errors == 0 else f"✗ {errors} 个文件校验失败")
    return 0 if errors == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("full").add_argument("version")
    d = sub.add_parser("diff")
    d.add_argument("from_ref")
    d.add_argument("to_ref")
    sub.add_parser("verify").add_argument("pkg")
    args = ap.parse_args()

    repo = Path.cwd()
    out_root = repo / "release"
    if args.cmd == "full":
        pkg = make_full(repo, args.version, out_root)
        print(f"✅ Full 包: {pkg}")
    elif args.cmd == "diff":
        pkg = make_diff(repo, args.from_ref, args.to_ref, out_root)
        print(f"✅ Diff 包: {pkg}")
    elif args.cmd == "verify":
        sys.exit(verify(Path(args.pkg)))


if __name__ == "__main__":
    main()