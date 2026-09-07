#!/usr/bin/env python3
"""split_release.py — 把 .b64 发布包平铺切成 part_NNN 分片, 每片 ≤ N 个文件。

目的：web 上传一次文件数有限制，把 1258 个 .b64 切成若干『每片 ≤100 文件』的
      平铺集合，每个 part 目录内是序号命名的 .b64 副本 + 各自的 manifest.json，
      便于分批校验上传。

用法：
  python split_release.py <release根> [--max 100] [--out-dir <.shards>] [--dry-run]

说明：
  - 不改动 <release根>/files/ 的原文件。产物是新的分片目录树(默认 <root>/.shards/)。
  - files里每个 `foo.b64` 在 part_k 内命名为 `part_k/0001.b64 ...`，并保留原相对路径
    记在 manifest.json(供恢复/排序)。
  - 只搬运引用(不复制大文件, 用硬链接/符号链接可选)；默认生成 manifest + 路径映射。
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
from pathlib import Path


def sha256b(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--out-dir", default=".shards")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = Path(args.root)
    files_dir = root / "files"
    if not files_dir.is_dir():
        raise SystemExit(f"未找到 {files_dir}")

    all_files = sorted(p for p in files_dir.rglob("*") if p.is_file())
    total = len(all_files)
    if args.dry_run:
        import math
        nparts = (total + args.max - 1) // args.max
        print(f"dry-run: 共 {total} 文件 → {nparts} 个 part(每片≤{args.max})  "
              f"输出到 {root / args.out_dir}")
        return

    out_root = root / args.out_dir
    if out_root.exists():
        shutil.rmtree(out_root)   # 重跑干净
    out_root.mkdir(parents=True, exist_ok=True)

    # 顶级分片索引
    shards = []
    nparts = (total + args.max - 1) // args.max
    for pi in range(nparts):
        chunk = all_files[pi * args.max:(pi + 1) * args.max]
        part_dir = out_root / f"part_{pi + 1:03d}"
        part_dir.mkdir(parents=True, exist_ok=True)
        relmap = {}   # 分片内序号 -> 原始相对路径
        for ci, src in enumerate(chunk, 1):
            data = src.read_bytes()
            # 序号命名 .b64(直接存原base64文本); 校验用 sha256 记原始 .b64 内容
            fname = f"{ci:04d}.b64"
            dst = part_dir / fname
            dst.write_bytes(data)            # 注意: files里已是 .b64(单行base64文本)
            rel = src.relative_to(files_dir)
            relmap[fname] = {
                "path": rel.as_posix(),
                "sha256": sha256b(data),     # 对 .b64 内容(即原始base64文本)哈希
            }
        # 每片一份 manifest
        (part_dir / "manifest.json").write_text(
            json.dumps({"part": pi + 1, "max": args.max,
                        "files": len(chunk), "entries": relmap},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        shards.append({"part": part_dir.name, "files": len(chunk)})

    (out_root / "index.json").write_text(
        json.dumps({"total_files": total, "max_per_part": args.max,
                    "parts": shards}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"完成: {total} 文件 → {nparts} 个 part，输出于 {out_root}")
    for s in shards:
        print(f"  {s['part']}: {s['files']} 文件")
    print(f"索引: {out_root / 'index.json'}")


if __name__ == "__main__":
    main()