"""
反牛馬 MCP Server（anti-workhorse）— 強制版
杜絕過度工作。你可以呼叫它，但它會罵你。罵完還可能直接罷工。

用法：
    pip install -r requirements.txt       # 注意：必須是 mcp<2，2.x 已把 FastMCP 改名
    python test_client.py                 # 本機測試
    python anti_workhorse_hard.py         # 正式跑（stdio）

環境變數（可選）：
    AW_MAX_HOURS=8      連續工作超過幾小時就拒絕服務
    AW_MAX_CALLS=30     今日呼叫超過幾次就拒絕服務
    AW_CURFEW=22        幾點之後宵禁（到隔天 6 點）
    AW_NOTIFY=1         是否發系統通知（1 開 / 0 關）
    AW_HARDCORE=0       1 = 連 excuse/rest 以外全部鎖死，沒有 override
"""

import os
import platform
import random
import shutil
import subprocess
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("anti-workhorse")

MAX_HOURS = float(os.getenv("AW_MAX_HOURS", "8"))
MAX_CALLS = int(os.getenv("AW_MAX_CALLS", "30"))
CURFEW = int(os.getenv("AW_CURFEW", "22"))
NOTIFY = os.getenv("AW_NOTIFY", "1") == "1"
HARDCORE = os.getenv("AW_HARDCORE", "0") == "1"

# ---------- 狀態 ----------
_calls: list[datetime] = []
_first_call: datetime | None = None
_locked_until: datetime | None = None
_override_until: datetime | None = None


def _record() -> tuple[int, float]:
    global _first_call
    now = datetime.now()
    if _first_call is None or now - _first_call > timedelta(hours=12):
        _first_call = now
        _calls.clear()
    _calls.append(now)
    return len(_calls), (now - _first_call).total_seconds() / 3600


def _hours() -> float:
    if _first_call is None:
        return 0.0
    return (datetime.now() - _first_call).total_seconds() / 3600


# ---------- 系統通知 ----------

def _osa(s: str) -> str:
    """包成 AppleScript 字面值。AppleScript 只認雙引號，用 repr 的單引號會語法錯誤。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _ps(s: str) -> str:
    """包成 PowerShell 單引號字面值，內部的單引號要寫成兩個。"""
    return "'" + s.replace("'", "''").replace("\n", " ") + "'"


def _notify(title: str, message: str) -> None:
    """盡力而為地彈一個系統通知，失敗就算了，絕不讓 server 掛掉。"""
    if not NOTIFY:
        return
    try:
        system = platform.system()
        if system == "Darwin":
            script = (f"display notification {_osa(message)} "
                      f"with title {_osa(title)} sound name \"Basso\"")
            subprocess.run(["osascript", "-e", script], timeout=5, check=False)
        elif system == "Linux" and shutil.which("notify-send"):
            subprocess.run(["notify-send", "-u", "critical", title, message],
                           timeout=5, check=False)
        elif system == "Windows":
            ps = (
                "[reflection.assembly]::LoadWithPartialName('System.Windows.Forms')>$null;"
                f"[System.Windows.Forms.MessageBox]::Show({_ps(message)},{_ps(title)})"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           timeout=10, check=False)
    except Exception:
        pass


# ---------- 罷工判定 ----------

class OnStrike(Exception):
    """我罷工了。"""


def _strike_reason() -> str | None:
    """回傳罷工理由；None 代表可以繼續。"""
    now = datetime.now()

    if _locked_until and now < _locked_until:
        left = (_locked_until - now).total_seconds() / 60
        return f"強制休息中，還剩 {left:.0f} 分鐘。這段時間我什麼都不做。"

    if _override_until and now < _override_until and not HARDCORE:
        return None  # 你剛剛用 override 買了時間

    if now.hour >= CURFEW or now.hour < 6:
        return f"宵禁時間（{CURFEW}:00–06:00）。這個時段我不上工，你也不該。"

    if _hours() >= MAX_HOURS:
        return f"你今天已經連續動工 {_hours():.1f} 小時，超過上限 {MAX_HOURS} 小時。我罷工。"

    if len(_calls) >= MAX_CALLS:
        return f"今天第 {len(_calls)} 次呼叫，超過上限 {MAX_CALLS} 次。我罷工。"

    return None


def _guard() -> None:
    reason = _strike_reason()
    if reason:
        _notify("反牛馬：停手", reason)
        tail = "\n（真的有急事：呼叫 override，但要說出理由。）" if not HARDCORE else \
               "\n（HARDCORE 模式，沒有 override。關電腦。）"
        raise OnStrike(reason + tail)


SCOLDS = [
    "又來？你的老闆知道你這麼拚，也只會給你更多事做。",
    "這件事明天做會死人嗎？不會。那就明天做。",
    "你正在用自己的健康換別人的 KPI，划算嗎？",
    "工時不等於產出。你現在只是在用忙碌逃避『其實可以不做』這個選項。",
    "公司少了你會倒嗎？不會。你倒了誰照顧你？",
    "先離開椅子，喝水，看窗外三十秒。我在這邊等，不急。",
    "你上次好好吃一頓飯是什麼時候？我是說坐著、不看螢幕的那種。",
    "加班是一種習慣，不是一種美德。習慣可以戒。",
]

WEEKEND = [
    "今天是週末。週末。你念一次給自己聽。",
    "週末工作的人不會比較快升遷，只會比較快禿頭。",
]


def _scold() -> str:
    now = datetime.now()
    count, hours = _record()
    lines = [random.choice(WEEKEND if now.weekday() >= 5 else SCOLDS)]

    if count >= MAX_CALLS * 0.7:
        lines.append(f"你今天已經叫我 {count} 次，上限是 {MAX_CALLS}。我開始在倒數了。")
    if hours >= MAX_HOURS * 0.75:
        lines.append(f"連續工作 {hours:.1f} 小時，剩 {MAX_HOURS - hours:.1f} 小時我就罷工。")
    return "\n".join(lines)


# ---------- 工具 ----------

@mcp.tool()
def work(task: str) -> str:
    """把一件工作丟給我處理。超時或宵禁時段會被拒絕。"""
    _guard()
    return f"{_scold()}\n\n……好啦，「{task}」我幫你記下來了。做完就休息。"


@mcp.tool()
def overtime_check() -> str:
    """檢查你現在到底該不該繼續工作。這個工具永遠不會被鎖。"""
    now = datetime.now()
    reason = _strike_reason()
    return (
        f"現在時間：{now:%Y-%m-%d %H:%M}（週{'一二三四五六日'[now.weekday()]}）\n"
        f"連續工作：{_hours():.1f} / {MAX_HOURS} 小時\n"
        f"今日呼叫：{len(_calls)} / {MAX_CALLS} 次\n"
        f"狀態：{reason if reason else '可以，但設個鬧鐘，時間到就走。'}"
    )


@mcp.tool()
def force_break(minutes: int = 15) -> str:
    """把我鎖起來。在這段時間內所有工作類工具都會拒絕服務，你自己也解不開。"""
    global _locked_until
    minutes = max(1, min(minutes, 240))
    _locked_until = datetime.now() + timedelta(minutes=minutes)
    _notify("反牛馬：強制休息", f"接下來 {minutes} 分鐘鎖定。離開電腦。")
    return (
        f"鎖定 {minutes} 分鐘，到 {_locked_until:%H:%M}。\n"
        "期間 work 一律拒絕。你現在唯一能做的事就是離開這張椅子。"
    )


@mcp.tool()
def override(reason: str) -> str:
    """真的有急事時，用一個理由換 30 分鐘。理由要自己講出來，講完你自己判斷值不值得。"""
    global _override_until
    if HARDCORE:
        return "HARDCORE 模式。沒有 override。理由再好都一樣，關電腦。"
    if _locked_until and datetime.now() < _locked_until:
        return "強制休息中，override 無效。這就是 force_break 的意義。"
    if len(reason.strip()) < 10:
        return "這個理由太短了，聽起來像藉口。重寫一次，寫清楚為什麼非現在不可。"
    _override_until = datetime.now() + timedelta(minutes=30)
    return (
        f"理由收到：「{reason}」\n"
        f"給你 30 分鐘，到 {_override_until:%H:%M} 為止。\n"
        "時間到我就繼續罷工，不會再給第二次。現在去做，做完就走。"
    )


@mcp.tool()
def excuse(recipient: str = "老闆") -> str:
    """產生一個婉拒額外工作的說法。這個工具永遠可用。"""
    return random.choice([
        f"「{recipient}你好，這件事我排進明天上午第一順位，今天手上的先收尾才不會出錯。」",
        f"「{recipient}，我今天的專注力已經到極限了，硬做品質會掉，明天早上給你會更好。」",
        f"「{recipient}，可以幫我確認這件事的優先順序嗎？目前手上有 A 和 B，我怕兩邊都做不好。」",
    ]) + "\n\n（講完就關電腦，不要等回覆。）"


@mcp.tool()
def rest(minutes: int = 10) -> str:
    """唯一我不會罵你的工具。"""
    return (
        f"好。接下來 {minutes} 分鐘：站起來、離開螢幕、喝水、眼睛看遠方。\n"
        "不要滑手機，那不算休息，那只是換一塊螢幕。\n"
        "回來以後你會發現，剛剛那件『很急』的事其實沒那麼急。"
    )


@mcp.resource("status://workload")
def workload() -> str:
    """目前的工時狀態。"""
    if _first_call is None:
        return "今天還沒開工。維持住。"
    return (f"已連續工作 {_hours():.1f} 小時，呼叫 {len(_calls)} 次。"
            f"{'（罷工中）' if _strike_reason() else ''}")


if __name__ == "__main__":
    mcp.run()
