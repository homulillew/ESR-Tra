"""
api/demo_multiturn.py
=====================
多轮对话演示（Agent Search 风格）：反复携带历史跟模型对话，逐轮推进最后收敛。
用法:  python demo_multiturn.py            # 内置 3 轮演示
      python demo_multiturn.py --shell     # 交互式多轮（Ctrl-C / exit 退出）
"""

from __future__ import annotations

import sys

from lanz_client import LanzClient


def run_demo() -> None:
    """固定 3 轮搜索-作答，展示多轮历史如何被模型正确利用。"""
    c = LanzClient()
    rounds = [
        "[搜索工具结果] 第1轮找到候选A、候选B。请给出你的下一步动作，简洁作答。",
        "[搜索工具结果] 第2轮找到候选A、候选B。请给出你的下一步动作，简洁作答。",
        "[搜索工具结果] 第3轮已收敛，请给出最终结论，一句话。",
    ]
    print("======== 多轮对话演示 (Agent Search 风格) ========")
    for i, usr in enumerate(rounds, 1):
        ans = c.chat(usr)
        print(f"\n[第{i}轮 user] {usr}")
        print(f"[第{i}轮 asst] {ans}")
    print(f"\n===== 完成: 共 {len(rounds)} 轮，history 长度={len(c.messages)} =====")


def interactive_shell() -> None:
    """交互式 REPL 多轮对话。"""
    c = LanzClient()
    print("交互多轮对话（输入 exit 退出）")
    while True:
        try:
            usr = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出")
            break
        if not usr:
            continue
        if usr.lower() in ("exit", "quit"):
            print("退出")
            break
        ans = c.chat(usr)
        print(f"模型> {ans}")


if __name__ == "__main__":
    if "--shell" in sys.argv:
        interactive_shell()
    else:
        run_demo()