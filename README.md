# FastAPI MCP-Style Server

Minimal FastAPI implementation that mimics a subset of Model Context Protocol (MCP) functionality.

## Features
- Echo-style POST `/mcp` endpoint returning structured response (id, status, outputs)
- JSON-RPC 2.0 endpoint `/mcp/rpc` supporting:
  - `mcp.list_tools`
  - `mcp.call_tool` (tools: `echo`, `uppercase`)
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

## Run Tests
```bash
pytest -q
```

## Next Ideas
- Streaming (SSE) outputs
- Prompts/resources primitives
- Auth layer (OAuth / API key)
- Tool change events
