# 反牛馬 MCP（anti-workhorse）

一個會罵你、還會直接罷工的 MCP server。杜絕過度工作。

工作時數超標、呼叫次數超標、或進入宵禁時段，它就拒絕服務。
`force_break` 甚至會把自己鎖住，鎖住期間連 `override` 都無效——這是刻意的。

## 工具

| 工具 | 說明 |
|---|---|
| `work(task)` | 把工作丟給它。會先罵你，超標時直接拒絕 |
| `overtime_check()` | 看現在到底該不該繼續。永遠不會被鎖 |
| `force_break(minutes)` | 把它鎖起來，期間 `work` 一律拒絕，你自己也解不開 |
| `override(reason)` | 真有急事，用一個理由換 30 分鐘。理由太短會被打回 |
| `excuse(recipient)` | 產生一個婉拒額外工作的說法。永遠可用 |
| `rest(minutes)` | 唯一不會罵你的工具 |

另有資源 `status://workload` 顯示目前工時狀態。

## 安裝

需要 Python 3.10+。

```bash
pip install -r requirements.txt
```

> **請勿直接 `pip install mcp`。** 最新的 2.x 把 `FastMCP` 改名成 `MCPServer`，
> 本專案的 `from mcp.server.fastmcp import FastMCP` 會直接 import 失敗。
> `requirements.txt` 已鎖 `mcp[cli]<2`。

## 接到 Claude Code

```bash
claude mcp add anti-workhorse -- /path/to/python /path/to/anti_workhorse_hard.py
```

`/path/to/python` 請填你安裝好 mcp 的那個環境的 python（conda env 或 venv 的絕對路徑）。

這是 stdio transport，完全在本機跑：client 會把它當子行程啟動，不需要 port、網域或任何部署。

## 設定（環境變數）

| 變數 | 預設 | 說明 |
|---|---|---|
| `AW_MAX_HOURS` | `8` | 連續工作超過幾小時就拒絕服務 |
| `AW_MAX_CALLS` | `30` | 今日呼叫超過幾次就拒絕服務 |
| `AW_CURFEW` | `22` | 幾點之後宵禁（到隔天 6 點） |
| `AW_NOTIFY` | `1` | 是否發系統通知（1 開 / 0 關） |
| `AW_HARDCORE` | `0` | `1` = 除了 `excuse` / `rest` 全部鎖死，沒有 override |

## 測試

`test_client.py` 會用 stdio 把 server 當子行程拉起來，列出工具、逐一呼叫並印出結果：

```bash
python test_client.py
```

門檻預設要跑 8 小時才會罷工，測試時用環境變數壓低就能在幾秒內看到各分支：

```bash
AW_MAX_CALLS=4 python test_client.py          # 次數罷工 + 倒數警告
AW_MAX_HOURS=0.001 python test_client.py      # 工時罷工
AW_CURFEW=10 python test_client.py            # 宵禁（設成比現在小的整數）
AW_HARDCORE=1 AW_CURFEW=10 python test_client.py   # override 失效
```

想要點按鈕的圖形介面，用 MCP Inspector。**不要用 `mcp dev`**——它內部寫死 `uv run --with mcp`，
沒有 uv 會失敗，有 uv 也會替你抓到不相容的 mcp 2.x。直接指定你自己的 python：

```bash
npx @modelcontextprotocol/inspector /path/to/python anti_workhorse_hard.py
```

## 已知限制

狀態（工時、呼叫次數、鎖定時間）存在記憶體裡，重啟 client 就會歸零。
換句話說，你想賴掉 `force_break` 隨時可以重開——但你會知道自己在幹嘛。
