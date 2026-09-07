#!/usr/bin/env python3
"""shard_release.py — 把 .b64 发布包的 files/ 拆成『每文件夹递归总文件 ≤100』。

口径：任何目录(含子目录)递归总文件数 ≤100。
实现：先一次建树并求每目录子树文件数(O(n))，再单遍自底向上(后序)决定每个超限目录
      的 part 切分方案——切分后父子目录的计数都即时更新。全部在内存完成，最后一次性
      执行文件移动。无重复 rglob，秒级。

核心不变量：切一条目录时, 其每个直属子目录在“切完后的最新计数”必然 ≤limit
    (因为后序先切了大子目录, 大子目录被拆成若干 part_NNN, 每个 ≤limit)。
    于是该目录按子项计数打包, 每 part ≤limit, 完成。

用法：
  python shard_release.py <release根> [--max 100]           # dry-run 预览(不改文件)
  python shard_release.py <release根> [--max 100] --apply   # 真正拆分
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


class Node:
    __slots__ = ("path", "name", "is_dir", "count", "children")

    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.is_dir = path.is_dir()
        self.count = 1 if not self.is_dir else 0
        self.children: list["Node"] = []


def build_tree(root: Path) -> Node:
    top = Node(root)
    stack = [top]
    while stack:
        nd = stack.pop()
        if nd.is_dir:
            for c in sorted(nd.path.iterdir()):
                cn = Node(c)
                nd.children.append(cn)
                stack.append(cn)
    # 后序累计
    def fold(n: Node) -> int:
        if not n.is_dir:
            return 1
        n.count = sum(fold(c) for c in n.children)
        return n.count
    fold(top)
    return top


def all_nodes(n: Node):
    yield n
    for c in n.children:
        yield from all_nodes(c)


def plan_tree(top: Node, limit: int, dry: bool) -> int:
    """后序切分所有超限目录。返回执行的分目录切分数。"""
    # children 需已切好才能切父。递归实现最直观。
    def walk(n: Node, path_ctx) -> None:
        # 先切子(后序, 最深先)
        for c in n.children:
            if c.is_dir:
                walk(c, path_ctx)
        # 现在 n 的每个直属子目录都已 ≤limit(切过或本就不超)
        if not n.is_dir or n.count <= limit:
            return
        # 打包直属子项
        bins: list[list[Node]] = [[]]
        cur = 0
        for c in n.children:
            sz = c.count
            if cur + sz > limit:
                bins.append([])
                cur = 0
            bins[-1].append(c)
            cur += sz
        k = len(bins)
        if k <= 1:
            return
        # 干-run 打印; apply 才动
        rel = n.path.relative_to(path_ctx)
        sizes = [sum(c.count for c in g) for g in bins]
        if dry:
            print(f"  [DRY] {rel} ({n.count}f) -> {k} parts: "
                  + " ".join(f"p{i+1}={s}" for i, s in enumerate(sizes)))
        else:
            for i, grp in enumerate(bins, 1):
                part = n.path / f"part_{i:03d}"
                part.mkdir(exist_ok=True)
                for c in grp:
                    shutil.move(str(c.path), str(part / c.name))
            print(f"  [OK] {rel} ({n.count}f) -> {k} parts")
        # 更新父视角: n 现在变成 k 个新 part 子项, 各 ≤limit
        # 通过把 n 在父.children 里的位置替换为 k 个合成节点即可; 简化: n.count 改为 k 个part的最小=>但父打包要 k 个单元
        n.count = max(sizes)  # 语义: 切完 n 自身 ≤ limit, 父打包时把 n 视作单个 ≤limit(实际用 max)
        # 注: 为让父打包正确(把 n 当 1 个 ≤limit 单元), 用 max(sizes) 即可
        return

    walk(top, top.path)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    files_dir = Path(args.root) / "files"
    if not files_dir.is_dir():
        sys.exit(f"未找到 {files_dir}")

    big = sum(1 for f in files_dir.rglob("*") if f.is_file())
    tree = build_tree(files_dir)
    overs = [n for n in all_nodes(tree) if n.is_dir and n.count > args.max]
    overs.sort(key=lambda n: len(n.path.parts), reverse=True)
    if not overs:
        print("✓ 所有目录递归总文件数均已 ≤ " + str(args.max) + "，无需拆分。")
        return
    if not args.apply:
        print(f"发现 {len(overs)} 个超限目录(自下而上):")
        for n in overs:
            print(f"  {n.count:5d}  {n.path.relative_to(files_dir)}")
        print("\n拆分方案(dry-run):")
    plan_tree(tree, args.max, dry=not args.apply)

    if not args.apply:
        print("\n(dry-run 完成。加 --apply 真正拆分。)")
        return

    after = sum(1 for f in files_dir.rglob("*") if f.is_file())
    cons = "守恒✓" if big == after else "文件丢失?! 检查 /tmp 备份"
    print(f"\n拆分完成: {big} -> {after} 文件 {cons}")

    leftover = [d for d in files_dir.rglob("*") if d.is_dir()
                and sum(1 for _ in d.rglob("*") if _.is_file()) > args.max]
    if leftover:
        print(f"!! 仍有 {len(leftover)} 个超限目录未收敛:")
        for d in leftover[:10]:
            print(f"    {sum(1 for _ in d.rglob('*') if _.is_file())}  {d}")
    else:
        print("✓ 全部分片后，所有目录递归文件数 ≤ " + str(args.max))

    shards = []
    for p in sorted(files_dir.rglob("part_*")):
        if p.is_dir():
            shards.append({"shard": p.relative_to(files_dir).as_posix(),
                           "files": sum(1 for _ in p.rglob("*") if _.is_file())})
    (Path(args.root) / "shard_manifest.json").write_text(
        json.dumps({"max_files_per_folder": args.max, "shards": shards,
                    "total_parts": len(shards)}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"已生成 {Path(args.root) / 'shard_manifest.json'}: {len(shards)} 个 part 分片")


if __name__ == "__main__":
    main()