from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
import uuid
import logging

# Configure basic logging
logger = logging.getLogger("mcp")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

app = FastAPI()


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
    return {"message": "FastAPI MCP Server is running"}


def _derive_output_text(raw: Any) -> str:
    """Derive a simple text output from the provided inputs.

    If inputs is a dict containing a 'text' key, echo that value.
    Otherwise, fallback to stringifying the entire object.
    """
    try:
        if isinstance(raw, dict) and "text" in raw:
            return str(raw["text"])  # ensure always string
        return str(raw)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("Failed to derive output text: %s", e)
        return ""


# Support both /mcp and /mcp/ paths for POST
@app.post("/mcp", response_model=MCPResponse)
@app.post("/mcp/", response_model=MCPResponse)
async def mcp_endpoint(req: MCPRequest):
    """Minimal MCP-like handler returning a structured response."""
    if req.inputs is None:
        raise HTTPException(status_code=400, detail="`inputs` field is required")

    run_id = str(uuid.uuid4())
    output_text = _derive_output_text(req.inputs)

    response = MCPResponse(
        id=run_id,
        status="succeeded",
        model=req.model,
        outputs=[MCPOutput(type="text", content=output_text)],
    )

    logger.info("Processed MCP request id=%s model=%s", run_id, req.model)
    return response


@app.get("/mcp")
@app.get("/mcp/")
def mcp_get():
    """Helpful usage info for GET callers (instead of 405)."""
    return {
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
    text = arguments.get("text")
    if text is None:
        raise ValueError("'text' field required")
    return {"type": "text", "content": str(text)}


def _tool_upper(arguments: Dict[str, Any]) -> Dict[str, Any]:
    text = arguments.get("text")
    if text is None:
        raise ValueError("'text' field required")
    return {"type": "text", "content": str(text).upper()}


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
}


def _jsonrpc_error(id_val, code: int, message: str, data: Any = None):
    return JSONRPCError(id=id_val, error=JSONRPCErrorObj(code=code, message=message, data=data))


@app.post("/mcp/rpc")
async def mcp_rpc(req: JSONRPCRequest):
    """Very small subset of MCP-like JSON-RPC interface.

    Supported methods:
    - mcp.list_tools -> { tools: [ { name, description, input_schema } ] }
    - mcp.call_tool (params: { name: str, arguments: object }) -> { outputs: [ {type, content} ] }
    """
    if req.jsonrpc != "2.0":
        return _jsonrpc_error(req.id, -32600, "Invalid JSON-RPC version")

    method = req.method
    params = req.params or {}

    if method == "mcp.list_tools":
        tools = [t["meta"].model_dump() for t in TOOLS.values()]
        return JSONRPCSuccess(id=req.id, result={"tools": tools})

    if method == "mcp.call_tool":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            return _jsonrpc_error(req.id, -32602, "Missing 'name' in params")
        tool_entry = TOOLS.get(name)
        if not tool_entry:
            return _jsonrpc_error(req.id, -32601, f"Tool '{name}' not found")
        try:
            output = tool_entry["callable"](arguments)
            return JSONRPCSuccess(id=req.id, result={"outputs": [output]})
        except ValueError as ve:
            return _jsonrpc_error(req.id, -32602, str(ve))
        except Exception as e:  # pragma: no cover
            logger.exception("Tool execution error")
            return _jsonrpc_error(req.id, -32000, "Tool execution failure", data=str(e))

    # Method not found
    return _jsonrpc_error(req.id, -32601, f"Method '{method}' not found")
