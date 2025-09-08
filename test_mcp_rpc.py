from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_rpc_list_tools():
    resp = client.post("/mcp/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "mcp.list_tools"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["tools"]
    names = {t["name"] for t in data["result"]["tools"]}
    assert {"echo", "uppercase"}.issubset(names)


def test_rpc_call_tool_echo():
    resp = client.post(
        "/mcp/rpc",
        json={
            "jsonrpc": "2.0",
            "id": "abc",
            "method": "mcp.call_tool",
            "params": {"name": "echo", "arguments": {"text": "hello"}},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"]["outputs"][0]["content"] == "hello"


def test_rpc_call_tool_missing_arg():
    resp = client.post(
        "/mcp/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 99,
            "method": "mcp.call_tool",
            "params": {"name": "echo", "arguments": {}},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["error"]["code"] == -32602
    assert "required" in data["error"]["message"]
