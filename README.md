---
title: MCP Market Analyst
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# 📈 MCP Market Analyst

**mcp-market-analyst** is a Model Context Protocol (MCP) Server designed to connect LLM clients (such as Claude Desktop) with real-time and historical financial market data via Server-Sent Events (SSE). 

This server provides seamless access to cryptocurrency candlestick data, global stocks, and foreign exchange (forex) pairs.

---

## 🛠️ Tools & Specifications

The server registers and exposes the following two primary tools:

### 1. `get_crypto_candles`
Fetches real-time and historical cryptocurrency candlestick (OHLCV) data from the Binance Public REST API.
* **Arguments**:
  - `symbol` (string, required): The cryptocurrency trading pair in uppercase, e.g., `"BTCUSDT"`, `"ETHUSDT"`.
  - `interval` (string, optional, default: `"1h"`): Candlestick interval. Choices: `"1m"`, `"5m"`, `"15m"`, `"1h"`, `"1d"`.
  - `limit` (integer, optional, default: `50`, max: `500`): Number of candles to return.

### 2. `get_stock_candles`
Fetches historical global stock market or forex data using the `yfinance` library.
* **Arguments**:
  - `ticker` (string, required): Stock ticker symbol (e.g., `"AAPL"`, `"TSLA"`, `"BBCA.JK"`) or forex pair (e.g., `"EURUSD=X"`).
  - `period` (string, optional, default: `"1mo"`): Historical data period. Choices: `"1d"`, `"5d"`, `"1mo"`, `"3mo"`, `"1y"`.
  - `interval` (string, optional, default: `"1d"`): Data interval. Choices: `"1m"`, `"5m"`, `"15m"`, `"1h"`, `"1d"`.

---

## 🔌 Integrating with Claude Web (claude.ai)

Since this server is hosted as a FastAPI/Docker app on Hugging Face Spaces, it does not use Gradio. Therefore, you cannot connect it using the native "Hugging Face" connector in Claude Web (which expects Gradio). Instead, use the **Custom Connectors** feature in Claude Web:

1. Open **Claude.ai** in your browser and go to your **Settings**.
2. Navigate to **Connectors** (or developer tools) and select **Add Custom Connector**.
3. Under the **Remote MCP server URL** field, enter your direct SSE endpoint:
   `https://lefrandbima-mcp-market-analyst.hf.space/sse`
4. Save and authorize the connection.

---

## 🔌 Integrating with Claude Desktop

To connect this remote MCP server to your local Claude Desktop client, follow the steps below:

### 1. Open your Claude Desktop Config File
The configuration file is typically located at:
* **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
* **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### 2. Add the MCP Server Configuration
Insert the following JSON snippet into the file:

```json
{
  "mcpServers": {
    "mcp-market-analyst": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/client-cli",
        "https://lefrandbima-mcp-market-analyst.hf.space/sse"
      ]
    }
  }
}
```

### 3. Restart Claude Desktop
Close and reopen your Claude Desktop application. A new hammer icon will appear in the input chat area.

---

## 🔌 Integrating with Cursor / VS Code Extensions (Cline, Roo Code)

You can connect this MCP server to other agents like **Cursor** or VS Code extensions:

### Option A: Remote SSE Connection (Fastest)
In your agent settings (e.g., Cursor Settings > Features > MCP), add a new MCP server with the following:
* **Name**: `mcp-market-analyst`
* **Type**: `sse`
* **URL**: `https://lefrandbima-mcp-market-analyst.hf.space/sse`

### Option B: Local Stdio Connection (Recommended for Local Dev)
If running locally, you can run the server using `uvicorn app:app --port 7860` and add this configuration:
* **Name**: `mcp-market-analyst`
* **Type**: `command`
* **Command**: `python /path/to/your/project/app.py` (or use `uvicorn` / `npx`)

---

## 🔍 Health Check & Verification
You can verify the status of the server using the public endpoints:
* **Health Check**: `GET https://lefrandbima-mcp-market-analyst.hf.space/`
* **SSE Endpoint**: `GET https://lefrandbima-mcp-market-analyst.hf.space/sse`