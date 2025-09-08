from fastapi.testclient import TestClient

from main import app


def test_mcp_echo_text():
    client = TestClient(app)
    resp = client.post("/mcp", json={"inputs": {"text": "hello"}})
    assert resp.status_code == 200
    j = resp.json()
    assert j["status"] == "succeeded"
    assert j["outputs"][0]["content"] == "hello"


def test_mcp_missing_inputs():
    client = TestClient(app)
    resp = client.post("/mcp", json={})
    assert resp.status_code == 400
    assert "inputs" in resp.json()["detail"]
