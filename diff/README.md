# Code-L 版本管理（offline git + diff 分包）

> 由于无法连外网 GitHub，这里用**本地 git 仓库**做版本管理，并用 **`git bundle`** 生成**可手动上传的单文件包**用于分发与备份。

## 双机制

| 机制 | 作用 | 使用方式 |
|------|------|---------|
| **本地 git 仓库** | 精确记录每个版本、`git diff` 看任何两次改动 | 每次改代码后 `git add -A && git commit` |
| **`diff/bundle/` 分包** | 把某版本打成**单个文件**，可手动拷走/上传到别处（离线替代 push） | 见下方「手动分发」 |

## 快速上手

```bash
# 1. 改完代码后，把改动固化为一个版本
cd /data1/ESR-GRPO-Code-L
git add -A
git commit -m "V2: <本次改动说明>"
git tag -a V2 -m "V2: <摘要>"        # 给这个版本打 tag，固化版本引用
bash scripts/cllog.sh "V2|摘要"        # 记录进 CHANGELOG（自动生成 bundle）

# 2. 看本次改动 vs 上个版本
git log --oneline -5
git diff V1 V2    # 精确看任意两版本差异

# 3. 手动分发（生成单个 .bundle 文件供上传，含完整分支历史）
bash diff/make_bundle.sh      # 缺省打当前分支(main)完整历史
```

> bundle 始终包含**完整分支历史**（V0→当前 HEAD 全部 commit），`clone` 后即可回溯任版本。
> 传入的 REF/tag 仅用于文件名命名（如 `code-l-V1-...`），不截断历史。

## 手动分发（离线替代 push）

在 `Code-L/diff/bundle/` 下生成一个 `code-l-<分支名>-<日期>.bundle` **单文件**，把这个文件手动拷到目标机器后：

```bash
# 目标机器：从 bundle 恢复完整仓库（含全部历史）
git clone code-l-main-2026-09-04.bundle code-l-local

# 或：只取当前工作区快照（无需历史）
git clone --branch main code-l-main-2026-09-04.bundle code-l-snapshot
```

bundle 是**自包含**的（含所有 commit + 引用），比一堆 diff 文件可靠得多。

## 版本记录

每次发版本，在 `CHANGELOG.md` 里追加一行（用 `scripts/cllog.sh [TAG|摘要]` 或手写）：

```
| 版本 tag | commit | 日期 | 改动摘要 | bundle 文件 |
|----------|--------|------|---------|-------------|
| V1 | 648b6b8 | 2026-09-04 | 离线版本管理设施 | code-l-main-...-61a0487.bundle |
```

> bundle 恒定含完整分支历史；文件名由 `git describe` 决定（无精确 tag 时回退分支名 `main`）。
> 想发带版本号的 bundle 时，先 `git tag -a Vn -m ...` 再 `make_bundle.sh Vn` 即可让文件名带版本号。

## 已排除进 git（仍在磁盘）

- `results/exp1/` —— 实验1最早的 126MB 轨迹石库（无 diff 价值，体积大）
- `*.log`、`__pycache__/`、`.pytest_cache/` —— 运行/缓存产物