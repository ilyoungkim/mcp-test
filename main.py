from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
import uuid
import logging
import pymysql
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

# Configure basic logging
logger = logging.getLogger("mcp")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")


LOG_TRUNCATE = 300


def _truncate(obj, limit: int = LOG_TRUNCATE):
    try:
        s = str(obj)
    except Exception:
        return "<unrepresentable>"
    return s if len(s) <= limit else s[: limit - 3] + "..."

app = FastAPI()

# ---------------------------------------------------------------------------
# Database (MariaDB) Configuration (simple non-pooled connections)
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "192.168.31.136",
    "port": 3306,
    "user": "fortune",
    "password": "user!1234@abcd",
    "database": "manse",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


@contextmanager
def get_db_cursor():
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception as e:  # pragma: no cover
        logger.exception("DB operation failed")
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:  # pragma: no cover
                pass


class MCPRequest(BaseModel):
    """Incoming MCP-style request body."""
    model: Optional[str] = Field(default=None, description="Model identifier (optional)")
    inputs: Optional[Any] = Field(default=None, description="Arbitrary input payload; requires 'inputs' root field")
    instructions: Optional[str] = Field(default=None, description="Optional instructions for processing")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata dictionary")


class MCPOutput(BaseModel):
    type: str = Field(description="Output type, e.g., 'text'")
    content: str = Field(description="Output content text")


class MCPResponse(BaseModel):
    id: str
    status: str
    model: Optional[str]
    outputs: List[MCPOutput]


@app.get("/")
def read_root():
    logger.debug("/ root endpoint accessed")
    resp = {"message": "FastAPI MCP Server is running"}
    logger.debug("/ root response=%s", resp)
    return resp


def _derive_output_text(raw: Any) -> str:
    """Derive a simple text output from the provided inputs.

    If inputs is a dict containing a 'text' key, echo that value.
    Otherwise, fallback to stringifying the entire object.
    """
    logger.debug("_derive_output_text raw_type=%s raw=%s", type(raw).__name__, _truncate(raw))
    try:
        if isinstance(raw, dict) and "text" in raw:
            logger.debug("_derive_output_text branch=dict-with-text")
            return str(raw["text"])  # ensure always string
        logger.debug("_derive_output_text branch=generic-cast")
        return str(raw)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("Failed to derive output text: %s", e)
        return ""


# Support both /mcp and /mcp/ paths for POST
@app.post("/mcp", response_model=MCPResponse)
@app.post("/mcp/", response_model=MCPResponse)
async def mcp_endpoint(req: MCPRequest):
    """Minimal MCP-like handler returning a structured response."""
    logger.debug("/mcp POST received body=%s", _truncate(req.model_dump()))
    if req.inputs is None:
        logger.warning("/mcp POST missing 'inputs'")
        raise HTTPException(status_code=400, detail="`inputs` field is required")

    run_id = str(uuid.uuid4())
    logger.debug("/mcp assigned run_id=%s", run_id)
    output_text = _derive_output_text(req.inputs)
    logger.debug("/mcp derived output_text=%s", _truncate(output_text))

    response = MCPResponse(
        id=run_id,
        status="succeeded",
        model=req.model,
        outputs=[MCPOutput(type="text", content=output_text)],
    )

    logger.info("/mcp completed id=%s model=%s", run_id, req.model)
    logger.debug("/mcp response=%s", _truncate(response.model_dump()))
    return response


@app.get("/mcp")
@app.get("/mcp/")
def mcp_get():
    """Helpful usage info for GET callers (instead of 405)."""
    logger.debug("/mcp GET accessed")
    resp = {
        "detail": "Use POST /mcp with JSON body. Example: {\"inputs\": {\"text\": \"hello\"}}",
        "allowed_methods": ["POST"],
        "schema": {
            "request": {
                "model": "string?",
                "inputs": "any (required)",
                "instructions": "string?",
                "metadata": "object?",
            },
            "response": {
                "id": "uuid",
                "status": "succeeded|failed",
                "model": "string?",
                "outputs": [
                    {"type": "text", "content": "string"}
                ],
            },
        },
    }
    logger.debug("/mcp GET response=%s", _truncate(resp))
    return resp

# ---------------------- JSON-RPC (minimal MCP-style) ----------------------
from pydantic import BaseModel
from typing import Union


class JSONRPCRequest(BaseModel):
    jsonrpc: str
    id: Union[str, int, None]
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCSuccess(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int, None]
    result: Any


class JSONRPCErrorObj(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCError(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int, None]
    error: JSONRPCErrorObj


class Tool(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


def _tool_echo(arguments: Dict[str, Any]) -> Dict[str, Any]:
    logger.debug("tool echo arguments=%s", _truncate(arguments))
    text = arguments.get("text")
    if text is None:
        logger.debug("tool echo missing text -> error")
        raise ValueError("'text' field required")
    result = {"type": "text", "content": str(text)}
    logger.debug("tool echo result=%s", result)
    return result


def _tool_upper(arguments: Dict[str, Any]) -> Dict[str, Any]:
    logger.debug("tool uppercase arguments=%s", _truncate(arguments))
    text = arguments.get("text")
    if text is None:
        logger.debug("tool uppercase missing text -> error")
        raise ValueError("'text' field required")
    result = {"type": "text", "content": str(text).upper()}
    logger.debug("tool uppercase result=%s", result)
    return result


TOOLS: Dict[str, Dict[str, Any]] = {
    "echo": {
        "callable": _tool_echo,
        "meta": Tool(
            name="echo",
            description="Echo back the provided text",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        ),
    },
    "uppercase": {
        "callable": _tool_upper,
        "meta": Tool(
            name="uppercase",
            description="Return the text in uppercase",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        ),
    },
    "query_manse": {
        "callable": lambda args: _tool_query_manse(args),
        "meta": Tool(
            name="query_manse",
            description="Run a SELECT query on manse.manse_data table with optional filters (limit default 10)",
            input_schema={
                "type": "object",
                "properties": {
                    "columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to select"},
                    "where": {"type": "string", "description": "Raw SQL WHERE clause without 'WHERE'"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 10},
                },
            },
        ),
    },
}


def _tool_query_manse(arguments: Dict[str, Any]) -> Dict[str, Any]:
    logger.debug("tool query_manse arguments=%s", _truncate(arguments))
    columns = arguments.get("columns") or ["*"]
    where_clause = arguments.get("where")
    limit = arguments.get("limit") or 10
    if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns):
        raise ValueError("'columns' must be a list of strings")
    if not isinstance(limit, int) or limit < 1 or limit > 500:
        raise ValueError("'limit' must be int 1-500")

    select_part = ", ".join(columns)
    base_query = f"SELECT {select_part} FROM manse_data"
    params = []
    if where_clause:
        # NOTE: Danger: raw clause; for safer usage parametrize or parse. Here kept minimal per request.
        base_query += f" WHERE {where_clause}"
    base_query += " LIMIT %s"
    params.append(limit)

    logger.debug("query_manse executing sql=%s params=%s", base_query, params)
    try:
        with get_db_cursor() as cur:
            cur.execute(base_query, params)
            rows = cur.fetchall()
    except Exception as e:
        logger.debug("query_manse execution error=%s", e)
        raise ValueError("Database query failed")

    # Truncate row preview
    preview = rows[:3]
    logger.debug("query_manse rows_fetched=%d preview=%s", len(rows), _truncate(preview))
    return {"type": "json", "content": {"rows": rows, "count": len(rows)}}


def _jsonrpc_error(id_val, code: int, message: str, data: Any = None):
    logger.debug("jsonrpc error id=%s code=%s message=%s data=%s", id_val, code, message, _truncate(data))
    return JSONRPCError(id=id_val, error=JSONRPCErrorObj(code=code, message=message, data=data))


@app.post("/mcp/rpc")
async def mcp_rpc(req: JSONRPCRequest):
    """Very small subset of MCP-like JSON-RPC interface.

    Supported methods:
    - mcp.list_tools -> { tools: [ { name, description, input_schema } ] }
    - mcp.call_tool (params: { name: str, arguments: object }) -> { outputs: [ {type, content} ] }
    """
    logger.debug("/mcp/rpc received id=%s method=%s params=%s", req.id, req.method, _truncate(req.params))
    if req.jsonrpc != "2.0":
        logger.debug("/mcp/rpc invalid jsonrpc version=%s", req.jsonrpc)
        return _jsonrpc_error(req.id, -32600, "Invalid JSON-RPC version")

    method = req.method
    params = req.params or {}

    if method == "mcp.list_tools":
        logger.debug("/mcp/rpc listing tools")
        tools = [t["meta"].model_dump() for t in TOOLS.values()]
        logger.debug("/mcp/rpc tools_count=%d", len(tools))
        return JSONRPCSuccess(id=req.id, result={"tools": tools})

    if method == "mcp.call_tool":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        logger.debug("/mcp/rpc call_tool name=%s args=%s", name, _truncate(arguments))
        if not name:
            logger.debug("/mcp/rpc call_tool missing name")
            return _jsonrpc_error(req.id, -32602, "Missing 'name' in params")
        tool_entry = TOOLS.get(name)
        if not tool_entry:
            logger.debug("/mcp/rpc call_tool tool_not_found name=%s", name)
            return _jsonrpc_error(req.id, -32601, f"Tool '{name}' not found")
        try:
            output = tool_entry["callable"](arguments)
            logger.debug("/mcp/rpc call_tool success name=%s output=%s", name, output)
            return JSONRPCSuccess(id=req.id, result={"outputs": [output]})
        except ValueError as ve:
            logger.debug("/mcp/rpc call_tool validation_error name=%s error=%s", name, ve)
            return _jsonrpc_error(req.id, -32602, str(ve))
        except Exception as e:  # pragma: no cover
            logger.exception("Tool execution error")
            return _jsonrpc_error(req.id, -32000, "Tool execution failure", data=str(e))

    # Method not found
    logger.debug("/mcp/rpc method_not_found method=%s", method)
    return _jsonrpc_error(req.id, -32601, f"Method '{method}' not found")
