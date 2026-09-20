"""
反牛馬 MCP 的測試客戶端。
用 stdio 把 server 當子行程跑起來，列出工具、逐一呼叫，印出結果。

用法：
    python test_client.py            # 正常情境
    AW_MAX_CALLS=3 python test_client.py   # 壓低門檻，逼它罷工
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anti_workhorse_hard.py")


def show(title: str, result) -> None:
    print(f"\n=== {title} ===")
    if getattr(result, "isError", False):
        print("[被拒絕 / 罷工]")
    for c in result.content:
        print(getattr(c, "text", c))


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER],
        env={**os.environ, "AW_NOTIFY": os.getenv("AW_NOTIFY", "0")},  # 測試時預設關通知
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("工具清單：")
            for t in tools.tools:
                print(f"  - {t.name}: {t.description}")

            resources = await session.list_resources()
            print("\n資源清單：")
            for r in resources.resources:
                print(f"  - {r.uri}")

            show("overtime_check（開工前）", await session.call_tool("overtime_check", {}))
            show("work", await session.call_tool("work", {"task": "把季報表做完"}))
            show("excuse", await session.call_tool("excuse", {"recipient": "主管"}))
            show("rest", await session.call_tool("rest", {"minutes": 10}))

            # 理由太短 → 應該被打回
            show("override（爛理由）", await session.call_tool("override", {"reason": "很急"}))

            # 多敲幾次 work，觀察警告升溫 / 是否罷工
            for i in range(5):
                show(f"work #{i + 2}", await session.call_tool("work", {"task": f"雜事 {i}"}))

            show("overtime_check（工作後）", await session.call_tool("overtime_check", {}))

            # 鎖住 1 分鐘，之後 work 應該一律拒絕
            show("force_break(1)", await session.call_tool("force_break", {"minutes": 1}))
            show("work（鎖定中）", await session.call_tool("work", {"task": "偷做一點"}))
            show("override（鎖定中）", await session.call_tool("override", {"reason": "客戶現在就要這份報表，不做明天會開天窗"}))
            show("rest（鎖定中仍可用）", await session.call_tool("rest", {}))

            res = await session.read_resource("status://workload")
            print("\n=== resource status://workload ===")
            for c in res.contents:
                print(getattr(c, "text", c))


if __name__ == "__main__":
    asyncio.run(main())
