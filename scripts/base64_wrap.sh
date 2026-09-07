#!/usr/bin/env bash
# base64 文件编解码工具
# 用法:
#   ./base64_wrap.sh encode <文件或目录...>   # 文件内容 base64，后缀加 .b64
#   ./base64_wrap.sh decode <文件或目录...>   # 把 .b64 文件还原为原文件（去除 .b64 后缀）
set -euo pipefail

usage() {
    echo "用法: $0 {encode|decode} <文件或目录...>"
    echo "  encode: 文件内容 base64 编码，输出为 <原路径>.b64"
    echo "  decode: 把 .b64 文件解码还原，输出为去掉 .b64 后缀的文件"
    exit 1
}

[[ $# -ge 2 ]] || usage
MODE="$1"
shift

encode_file() {
    local src="$1"
    if [[ -f "$src.b64" ]]; then
        echo "跳过(已存在): $src.b64"
        return
    fi
    base64 -w0 "$src" > "$src.b64"
    echo "编码: $src -> $src.b64"
}

decode_file() {
    local src="$1"
    if [[ "$src" != *.b64 ]]; then
        echo "跳过(非 .b64): $src"
        return
    fi
    local out="${src%.b64}"
    if [[ -e "$out" ]]; then
        echo "跳过(目标已存在): $out"
        return
    fi
    # 解码前先校验内容是否为合法 base64，避免误破坏二进制
    if ! base64 -d "$src" > "$out" 2>/dev/null; then
        echo "失败(非法 base64): $src"
        rm -f "$out"
    else
        echo "解码: $src -> $out"
    fi
}

for p in "$@"; do
    if [[ -d "$p" ]]; then
        # 目录递归处理；跳过已生成的 .b64 再次编码
        while IFS= read -r -d '' f; do
            case "$MODE" in
                encode) [[ "$f" != *.b64 ]] && encode_file "$f" ;;
                decode) decode_file "$f" ;;
            esac
        done < <(find "$p" -type f -print0)
    elif [[ -f "$p" ]]; then
        case "$MODE" in
            encode) encode_file "$p" ;;
            decode) decode_file "$p" ;;
            *) usage ;;
        esac
    else
        echo "跳过(不存在): $p"
    fi
done