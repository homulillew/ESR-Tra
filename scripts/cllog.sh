#!/usr/bin/env bash
# 在 CHANGELOG.md 追加一条版本记录（含 bundle 文件名）
# 用法:  bash scripts/cllog.sh "V1|本次改动摘要"
# 可选第二参数指定 bundle 文件；缺省自动调用 make_bundle.sh 生成。

set -euo pipefail
cd "$(dirname "$0")/.."
MSG="${1:?用法: cllog.sh \"TAG|摘要\" [bundle文件名]}"
TAG="${MSG%%|*}"
SUMMARY="${MSG#*|}"
COMMIT="$(git rev-parse --short HEAD)"
STAMP="$(date +%F)"

BUNDLE_LINE="-"
if [ -n "${2:-}" ]; then
    BUNDLE_LINE="$2"
else
    bash diff/make_bundle.sh HEAD >/tmp/_cllog_bundle.txt 2>&1 || true
    BUNDLE_LINE="$(grep -oE 'code-l-[^ ]+\.bundle' /tmp/_cllog_bundle.txt | head -1 || true)"
    [ -n "$BUNDLE_LINE" ] || BUNDLE_LINE="-"
fi

mkdir -p diff
[ -f diff/CHANGELOG.md ] || printf '| 版本 | commit | 日期 | 改动摘要 | bundle 文件 |\n|------|--------|------|---------|-------------|\n' > diff/CHANGELOG.md
printf '| %s | %s | %s | %s | %s |\n' "$TAG" "$COMMIT" "$STAMP" "$SUMMARY" "$BUNDLE_LINE" >> diff/CHANGELOG.md
echo "✅ 已记录 : diff/CHANGELOG.md"
echo "   $TAG | $COMMIT | $STAMP | $SUMMARY | $BUNDLE_LINE"