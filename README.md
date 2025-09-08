# FastAPI MCP-Style Server

Minimal FastAPI implementation that mimics a subset of Model Context Protocol (MCP) functionality.

## Features
- Echo-style POST `/mcp` endpoint returning structured response (id, status, outputs)
- JSON-RPC 2.0 endpoint `/mcp/rpc` supporting:
  - `mcp.list_tools`
  - `mcp.call_tool` (tools: `echo`, `uppercase`, `query_manse`)
- GET usage helper `/mcp`
- Pydantic models for request/response
- Basic logging
- Tests (pytest) for REST + RPC

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## REST Usage
```bash
curl -X POST http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"inputs": {"text": "hello"}}'
```

## JSON-RPC Examples
List tools:
```bash
curl -X POST http://127.0.0.1:8000/mcp/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"mcp.list_tools"}'
```

Call echo:
```bash
curl -X POST http://127.0.0.1:8000/mcp/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"abc","method":"mcp.call_tool","params":{"name":"echo","arguments":{"text":"hello"}}}'
```

Call query_manse (first 5 rows):
```bash
curl -X POST http://127.0.0.1:8000/mcp/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"mcp.call_tool","params":{"name":"query_manse","arguments":{"limit":5}}}'
```

## Environment Variables (DB)
| Variable | Default | Description |
|----------|---------|-------------|
| MCP_DB_HOST | 192.168.31.136 | MariaDB host |
| MCP_DB_PORT | 3306 | MariaDB port |
| MCP_DB_USER |  | DB user |
| MCP_DB_PASSWORD |  | DB password |
| MCP_DB_NAME | manse | Database name |

Example run with overrides:
```bash
MCP_DB_HOST=127.0.0.1 MCP_DB_USER=app MCP_DB_PASSWORD=secret uvicorn main:app --reload
```

## Run Tests
```bash
pytest -q
```

## Next Ideas
- Streaming (SSE) outputs
- Prompts/resources primitives
- Auth layer (OAuth / API key)
- Tool change events
