#!/usr/bin/env bash
# 把指定 git 引用打成可手动上传的单文件 bundle，落到 diff/bundle/
# 用法:  bash diff/make_bundle.sh [REF]  （缺省 REF=HEAD，即当前版本）
# 命名: code-l-<最近tag或当前分支>-<日期>-<short-commit>.bundle

set -euo pipefail
cd "$(dirname "$0")/.."   # 回到 Code-L 根

REF="${1:-HEAD}"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
STAMP="$(date +%Y%m%d)"
SHORT="$(git rev-parse --short "$REF")"
# 若 REF 指向有 tag 的 commit 用 tag 名，否则用分支名
REFNAME="$(git describe --tags --exact-match "$REF" 2>/dev/null || echo "$BRANCH")"
OUT="diff/bundle/code-l-${REFNAME}-${STAMP}-${SHORT}.bundle"
mkdir -p diff/bundle

# 确认引用存在
git rev-parse --verify "$REF" >/dev/null 2>&1 || { echo "错误: 引用 '$REF' 不存在"; exit 1; }
# 若同名 bundle 已存在则先删，避免内容漂移混乱
[ -f "$OUT" ] && { echo "覆盖旧分发包: $OUT"; rm -f "$OUT"; }

git bundle create "$OUT" --branches >/dev/null 2>&1
SZ="$(du -h "$OUT" | cut -f1)"
COMMIT_MSG="$(git log -1 --format='%s' "$REF")"
echo "✅ 已生成分发包: $OUT ($SZ)"
echo "   对应版本 : $REFNAME @ $SHORT  「$COMMIT_MSG」"
echo "   手动上传到目标机后:  git clone $OUT <本地目录>"