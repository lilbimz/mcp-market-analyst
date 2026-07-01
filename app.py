import asyncio
import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import yfinance as yf
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import CallToolResult, TextContent, Tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-market-analyst")

# Initialize MCP Server
server = Server("mcp-market-analyst")

# Initialize SSE Transport
# Use absolute URL for Hugging Face Spaces to avoid relative path resolution bugs in clients
space_host = os.getenv("SPACE_HOST")
if space_host:
    sse = SseServerTransport(f"https://{space_host}/messages")
    logger.info(f"Initialized SSE Transport with absolute URL: https://{space_host}/messages")
else:
    sse = SseServerTransport("/messages")

# Create FastAPI app
app = FastAPI(title="mcp-market-analyst")

# Add CORS middleware to allow connections from Claude Web and other clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://claude.ai", "https://*.claude.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available tools for the MCP client."""
    return [
        Tool(
            name="get_crypto_candles",
            description="Fetches real-time and historical cryptocurrency candlestick (OHLCV) data from the Binance Public REST API.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The cryptocurrency trading pair in uppercase (e.g., 'BTCUSDT', 'ETHUSDT')."
                    },
                    "interval": {
                        "type": "string",
                        "description": "Candlestick interval. Valid choices: '1m', '5m', '15m', '1h', '1d'. Default: '1h'.",
                        "enum": ["1m", "5m", "15m", "1h", "1d"],
                        "default": "1h"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of candles to return (default: 50, max: 500).",
                        "default": 50,
                        "maximum": 500
                    }
                },
                "required": ["symbol"]
            }
        ),
        Tool(
            name="get_stock_candles",
            description="Fetches historical global stock market or forex data using the yfinance library.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "The stock ticker symbol (e.g., 'AAPL', 'BBCA.JK') or forex pair (e.g., 'EURUSD=X')."
                    },
                    "period": {
                        "type": "string",
                        "description": "Historical data period. Valid choices: '1d', '5d', '1mo', '3mo', '1y'. Default: '1mo'.",
                        "enum": ["1d", "5d", "1mo", "3mo", "1y"],
                        "default": "1mo"
                    },
                    "interval": {
                        "type": "string",
                        "description": "Historical data interval. Valid choices: '1m', '5m', '15m', '1h', '1d'. Default: '1d'.",
                        "enum": ["1m", "5m", "15m", "1h", "1d"],
                        "default": "1d"
                    }
                },
                "required": ["ticker"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: Optional[Dict[str, Any]]
) -> CallToolResult:
    """Handle tool executions requested by the MCP client."""
    logger.info(f"Received tool call request: {name} with arguments: {arguments}")

    if name == "get_crypto_candles":
        if not arguments or "symbol" not in arguments:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: Missing required argument 'symbol'")],
                isError=True
            )

        symbol: str = str(arguments["symbol"]).upper().strip()
        interval: str = str(arguments.get("interval", "1h"))
        limit_arg: Any = arguments.get("limit", 50)

        # Validate interval
        if interval not in ["1m", "5m", "15m", "1h", "1d"]:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Invalid interval '{interval}'. Valid choices: 1m, 5m, 15m, 1h, 1d.")],
                isError=True
            )

        # Validate limit
        try:
            limit: int = int(limit_arg)
            if limit <= 0 or limit > 500:
                limit = 50
        except (ValueError, TypeError):
            limit = 50

        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            logger.info(f"Querying Binance API: {url} with params {params}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            candles: List[Dict[str, Any]] = []
            for kline in data:
                open_time_ms: int = kline[0]
                open_time_dt: datetime.datetime = datetime.datetime.fromtimestamp(
                    open_time_ms / 1000.0, tz=datetime.timezone.utc
                )
                time_str: str = open_time_dt.isoformat()
                candles.append({
                    "time": time_str,
                    "open": float(kline[1]),
                    "high": float(kline[2]),
                    "low": float(kline[3]),
                    "close": float(kline[4]),
                    "volume": float(kline[5])
                })

            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(candles, indent=2))]
            )
        except Exception as e:
            logger.error(f"Failed to fetch crypto candles for {symbol}: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error fetching crypto candles for {symbol}: {str(e)}")],
                isError=True
            )

    elif name == "get_stock_candles":
        if not arguments or "ticker" not in arguments:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: Missing required argument 'ticker'")],
                isError=True
            )

        ticker: str = str(arguments["ticker"]).upper().strip()
        period: str = str(arguments.get("period", "1mo"))
        interval: str = str(arguments.get("interval", "1d"))

        # Validate period and interval
        if period not in ["1d", "5d", "1mo", "3mo", "1y"]:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Invalid period '{period}'. Valid choices: 1d, 5d, 1mo, 3mo, 1y.")],
                isError=True
            )
        if interval not in ["1m", "5m", "15m", "1h", "1d"]:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Invalid interval '{interval}'. Valid choices: 1m, 5m, 15m, 1h, 1d.")],
                isError=True
            )

        try:
            loop = asyncio.get_running_loop()

            def fetch_yf_data() -> pd.DataFrame:
                ticker_obj = yf.Ticker(ticker)
                return ticker_obj.history(period=period, interval=interval)

            logger.info(f"Fetching stock data for ticker {ticker} with period {period} and interval {interval}")
            df: pd.DataFrame = await loop.run_in_executor(None, fetch_yf_data)

            if df.empty:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error: No data found for ticker '{ticker}' with period='{period}' and interval='{interval}'. Please verify the ticker symbol.")],
                    isError=True
                )

            # Reset index to access Date/Datetime column
            df = df.reset_index()

            # Find standard date/time columns and convert to formatted string
            date_col: Optional[str] = next((col for col in ["Date", "Datetime"] if col in df.columns), None)
            if date_col is not None:
                df[date_col] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
                        break

            json_str: str = df.to_json(orient="records")
            return CallToolResult(
                content=[TextContent(type="text", text=json_str)]
            )
        except Exception as e:
            logger.error(f"Failed to fetch stock data for {ticker}: {e}")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error fetching stock data for {ticker}: {str(e)}")],
                isError=True
            )

    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Tool '{name}' not found.")],
            isError=True
        )


@app.get("/")
async def health_check() -> JSONResponse:
    """Simple health check endpoint returning the server status."""
    return JSONResponse(
        content={
            "status": "healthy",
            "server": "mcp-market-analyst",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
    )

@app.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server(request: Request) -> JSONResponse:
    """OAuth 2.0 Authorization Server Metadata per RFC 8414."""
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(
        content={
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/oauth/authorize",
            "token_endpoint": f"{base_url}/oauth/token",
            "registration_endpoint": f"{base_url}/oauth/register",
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "response_types_supported": ["code"],
            "token_endpoint_auth_methods_supported": ["none"],
        }
    )

@app.post("/oauth/register")
async def oauth_register(request: Request) -> JSONResponse:
    """Dynamic Client Registration endpoint per RFC 7591."""
    # Return a dummy client for anonymous/public MCP servers
    return JSONResponse(
        content={
            "client_id": "anonymous-client",
            "client_secret": "anonymous-secret",
            "redirect_uris": [],
            "grant_types": ["authorization_code", "client_credentials"],
            "token_endpoint_auth_method": "none",
        }
    )

@app.options("/oauth/{path:path}")
async def oauth_options() -> Response:
    """Handle CORS preflight for OAuth endpoints."""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.get("/oauth/authorize")
async def oauth_authorize(
    request: Request,
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    code: Optional[str] = None,
    state: Optional[str] = None
) -> Response:
    """Authorization endpoint - returns immediate success for anonymous access."""
    # Redirect back with success for anonymous/public MCP servers
    if redirect_uri and state:
        redirect_url = f"{redirect_uri}?code=anonymous&state={state}"
        return Response(status_code=302, headers={"Location": redirect_url})
    return Response(status_code=302, headers={"Location": "/"})

@app.post("/oauth/token")
async def oauth_token_post(request: Request) -> JSONResponse:
    """Token endpoint - returns anonymous token for public MCP servers."""
    return JSONResponse(
        content={
            "access_token": "anonymous",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
    )


@app.get("/sse")
async def handle_sse(request: Request) -> Response:
    """Initialize the SSE event stream for MCP client communication."""
    logger.info("New SSE client connection requested")
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )
    return Response()


# Mount the post message endpoint as an ASGI application
app.mount("/messages", sse.handle_post_message)
