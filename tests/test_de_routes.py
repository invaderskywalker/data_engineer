"""
Integration tests for /de/* (Data Engineer) API routes.

Runs against a live server. Default: http://localhost:8889
Override with: DE_BASE_URL=http://... pytest tests/test_de_routes.py -v

The /de/ routes do NOT require a JWT (no auth decorator on them),
so these tests work without any token.

Run all tests:
    pytest tests/test_de_routes.py -v

Run a specific class:
    pytest tests/test_de_routes.py::TestConnections -v

To test the full CRUD flow (needs a real Postgres DB), set env vars:
    DE_TEST_DB_HOST, DE_TEST_DB_PORT, DE_TEST_DB_NAME,
    DE_TEST_DB_USER, DE_TEST_DB_PASS  (DE_TEST_DB_SSL defaults to false)
"""

import os
import time
import pytest
import requests

# ─── Config ──────────────────────────────────────────────────────────────────

BASE_URL = os.getenv("DE_BASE_URL", "http://localhost:8889")
TIMEOUT = 15  # seconds
FAKE_UUID = "00000000-0000-0000-0000-000000000000"

# Optional: real DB credentials for full CRUD flow tests
TEST_DB = {
    "host": os.getenv("DE_TEST_DB_HOST", ""),
    "port": int(os.getenv("DE_TEST_DB_PORT", "5432")),
    "database": os.getenv("DE_TEST_DB_NAME", ""),
    "username": os.getenv("DE_TEST_DB_USER", ""),
    "password": os.getenv("DE_TEST_DB_PASS", ""),
    "ssl": os.getenv("DE_TEST_DB_SSL", "false").lower() == "true",
}
HAS_TEST_DB = all([TEST_DB["host"], TEST_DB["database"], TEST_DB["username"], TEST_DB["password"]])

# ─── Helpers ──────────────────────────────────────────────────────────────────

def get(path, **kwargs):
    return requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def post(path, **kwargs):
    return requests.post(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def delete(path, **kwargs):
    return requests.delete(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def assert_json_keys(data: dict, *keys):
    missing = [k for k in keys if k not in data]
    assert not missing, f"Response missing keys {missing}. Got: {list(data.keys())}"


# ─── Server reachability ──────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def check_server():
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        if r.status_code >= 500:
            pytest.exit(f"Server at {BASE_URL} is unhealthy (status {r.status_code})")
    except requests.ConnectionError:
        pytest.exit(
            f"Cannot reach server at {BASE_URL}. "
            "Start it with: gunicorn --timeout 120 -w 1 -k eventlet -b 0.0.0.0:8889 src.api.app.App:app"
        )


# ─── Connections ─────────────────────────────────────────────────────────────

class TestConnections:

    def test_list_returns_200_array(self):
        r = get("/de/connections")
        assert r.status_code == 200, f"[{r.status_code}] {r.text}"
        data = r.json()
        assert isinstance(data, list), f"Expected list, got: {type(data).__name__}"

    def test_list_connection_shape(self):
        """If there are connections in DB, validate their shape."""
        r = get("/de/connections")
        assert r.status_code == 200
        items = r.json()
        if items:
            conn = items[0]
            assert_json_keys(conn, "id", "name", "host", "port", "database",
                             "username", "ssl", "status", "created_at", "table_count")

    def test_get_nonexistent_returns_404(self):
        r = get(f"/de/connections/{FAKE_UUID}")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        assert "error" in r.json()

    def test_delete_nonexistent_returns_404(self):
        r = delete(f"/de/connections/{FAKE_UUID}")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_test_saved_nonexistent_returns_404(self):
        r = post(f"/de/connections/{FAKE_UUID}/test")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_get_schema_nonexistent_returns_404(self):
        r = get(f"/de/connections/{FAKE_UUID}/schema")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_refresh_schema_nonexistent_returns_404(self):
        r = post(f"/de/connections/{FAKE_UUID}/schema/refresh")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


# ─── Test Raw Connection ──────────────────────────────────────────────────────

class TestRawConnectionTest:

    def test_bad_host_returns_failure(self):
        r = post("/de/connections/test", json={
            "host": "127.0.0.1",
            "port": 19999,
            "database": "nonexistent_db",
            "username": "no_user",
            "password": "wrong_pass",
            "ssl": False,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert_json_keys(data, "success", "message")
        assert data["success"] is False, f"Expected failure, got: {data}"

    def test_connection_string_parse_and_fail(self):
        r = post("/de/connections/test", json={
            "connection_string": "postgresql://nobody:wrongpass@127.0.0.1:19999/nonexistent"
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["success"] is False

    def test_empty_body_returns_failure_not_500(self):
        """Sending empty body should fail gracefully (connection refused), not crash."""
        r = post("/de/connections/test", json={})
        assert r.status_code == 200, f"Expected 200 (even for empty body), got {r.status_code}: {r.text}"
        data = r.json()
        assert "success" in data

    @pytest.mark.skipif(not HAS_TEST_DB, reason="Set DE_TEST_DB_* env vars to run live connection test")
    def test_real_connection_succeeds(self):
        r = post("/de/connections/test", json=TEST_DB)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True, f"Real connection failed: {data.get('message')}"
        assert "table_count" in data


# ─── Sessions ─────────────────────────────────────────────────────────────────

class TestSessions:

    def test_list_returns_200_array(self):
        r = get("/de/sessions")
        assert r.status_code == 200, f"[{r.status_code}] {r.text}"
        assert isinstance(r.json(), list)

    def test_list_with_connection_filter(self):
        r = get(f"/de/sessions?connection_id={FAKE_UUID}")
        assert r.status_code == 200, f"[{r.status_code}] {r.text}"
        assert isinstance(r.json(), list)
        # With a fake UUID there should be 0 results
        assert r.json() == [], f"Expected empty list for fake conn_id, got: {r.json()}"

    def test_list_session_shape(self):
        r = get("/de/sessions")
        assert r.status_code == 200
        items = r.json()
        if items:
            sess = items[0]
            assert_json_keys(sess, "id", "connection_id", "title", "created_at", "run_count")

    def test_get_nonexistent_returns_404(self):
        r = get(f"/de/sessions/{FAKE_UUID}")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        assert "error" in r.json()


# ─── Runs ─────────────────────────────────────────────────────────────────────

class TestRuns:

    def test_get_nonexistent_returns_404(self):
        r = get(f"/de/runs/{FAKE_UUID}")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        assert "error" in r.json()

    def test_download_nonexistent_returns_404(self):
        r = get(f"/de/runs/{FAKE_UUID}/download")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
        assert "error" in r.json()


# ─── Ask endpoint ─────────────────────────────────────────────────────────────

class TestAsk:

    def test_missing_question_returns_400(self):
        """question field is required — should get 400 before even checking the connection."""
        r = post(f"/de/connections/{FAKE_UUID}/ask", json={})
        assert r.status_code == 400, f"Expected 400 for missing question, got {r.status_code}: {r.text}"
        assert "error" in r.json()

    def test_empty_question_returns_400(self):
        r = post(f"/de/connections/{FAKE_UUID}/ask", json={"question": "   "})
        assert r.status_code == 400, f"Expected 400 for blank question, got {r.status_code}: {r.text}"

    def test_nonexistent_connection_returns_404(self):
        r = post(f"/de/connections/{FAKE_UUID}/ask", json={"question": "How many rows?"})
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_invalid_session_id_returns_404(self):
        r = post(f"/de/connections/{FAKE_UUID}/ask", json={
            "question": "How many rows?",
            "session_id": FAKE_UUID,
        })
        # Either 404 (connection not found) or 404 (session not found)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


# ─── Full CRUD flow (needs real DB) ───────────────────────────────────────────

@pytest.mark.skipif(not HAS_TEST_DB, reason="Set DE_TEST_DB_* env vars to run full CRUD flow")
class TestFullCRUDFlow:
    """
    End-to-end flow: create connection → get → schema → ask → poll run → delete.
    Requires a reachable Postgres DB via DE_TEST_DB_* env vars.
    """

    conn_id = None
    run_id = None
    session_id = None

    def test_01_create_connection(self):
        r = post("/de/connections", json={
            "name": "pytest-test-conn",
            **TEST_DB,
        })
        assert r.status_code == 201, f"[{r.status_code}] {r.text}"
        data = r.json()
        assert_json_keys(data, "id", "name", "host", "port", "database", "status")
        assert data["status"] == "active"
        TestFullCRUDFlow.conn_id = data["id"]

    def test_02_get_connection(self):
        assert TestFullCRUDFlow.conn_id, "No conn_id from previous test"
        r = get(f"/de/connections/{TestFullCRUDFlow.conn_id}")
        assert r.status_code == 200, f"[{r.status_code}] {r.text}"
        data = r.json()
        assert data["id"] == TestFullCRUDFlow.conn_id
        assert data["name"] == "pytest-test-conn"

    def test_03_connection_in_list(self):
        r = get("/de/connections")
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert TestFullCRUDFlow.conn_id in ids, "Created connection not in list"

    def test_04_test_saved_connection(self):
        assert TestFullCRUDFlow.conn_id
        r = post(f"/de/connections/{TestFullCRUDFlow.conn_id}/test")
        assert r.status_code == 200, f"[{r.status_code}] {r.text}"
        data = r.json()
        assert data["success"] is True, f"Connection test failed: {data.get('message')}"

    def test_05_get_schema(self):
        assert TestFullCRUDFlow.conn_id
        # Schema might still be introspecting in background — wait briefly
        time.sleep(2)
        r = get(f"/de/connections/{TestFullCRUDFlow.conn_id}/schema")
        assert r.status_code == 200, f"[{r.status_code}] {r.text}"
        data = r.json()
        assert_json_keys(data, "tables", "relationships", "suggested_questions")
        assert isinstance(data["tables"], list)
        # sample_rows should be stripped from public response
        for tbl in data["tables"]:
            assert "sample_rows" not in tbl, "sample_rows should be stripped from schema response"

    def test_06_ask_creates_run(self):
        assert TestFullCRUDFlow.conn_id
        r = post(f"/de/connections/{TestFullCRUDFlow.conn_id}/ask", json={
            "question": "How many tables are there?",
        })
        assert r.status_code == 200, f"[{r.status_code}] {r.text}"
        data = r.json()
        assert_json_keys(data, "id", "session_id", "question", "status")
        assert data["status"] == "running"
        assert data["question"] == "How many tables are there?"
        TestFullCRUDFlow.run_id = data["id"]
        TestFullCRUDFlow.session_id = data["session_id"]

    def test_07_get_run_completes_or_fails(self):
        assert TestFullCRUDFlow.run_id
        # Poll for up to 15 seconds
        final = None
        for _ in range(15):
            time.sleep(1)
            r = get(f"/de/runs/{TestFullCRUDFlow.run_id}")
            assert r.status_code == 200, f"[{r.status_code}] {r.text}"
            data = r.json()
            if data["status"] in ("completed", "failed"):
                final = data
                break

        assert final is not None, "Run did not complete within 15 seconds"
        assert_json_keys(final, "id", "session_id", "question", "status",
                         "answer_text", "queries_executed", "created_at")
        # Currently the agent is a stub so it will be 'failed' — that's expected
        # This test passes either way; it just verifies the run reaches a terminal state
        print(f"\n  Run status: {final['status']}, error: {final.get('error_message')}")

    def test_08_session_has_run(self):
        assert TestFullCRUDFlow.session_id
        r = get(f"/de/sessions/{TestFullCRUDFlow.session_id}")
        assert r.status_code == 200, f"[{r.status_code}] {r.text}"
        data = r.json()
        assert_json_keys(data, "id", "connection_id", "title", "runs")
        assert isinstance(data["runs"], list)
        run_ids = [run["id"] for run in data["runs"]]
        assert TestFullCRUDFlow.run_id in run_ids, "Run not found in session"

    def test_09_session_in_list(self):
        r = get("/de/sessions")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert TestFullCRUDFlow.session_id in ids

    def test_10_session_filtered_by_connection(self):
        r = get(f"/de/sessions?connection_id={TestFullCRUDFlow.conn_id}")
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert TestFullCRUDFlow.session_id in ids

    def test_11_delete_connection(self):
        assert TestFullCRUDFlow.conn_id
        r = delete(f"/de/connections/{TestFullCRUDFlow.conn_id}")
        assert r.status_code == 204, f"Expected 204, got {r.status_code}: {r.text}"

    def test_12_deleted_connection_is_gone(self):
        assert TestFullCRUDFlow.conn_id
        r = get(f"/de/connections/{TestFullCRUDFlow.conn_id}")
        assert r.status_code == 404, f"Deleted connection should return 404, got {r.status_code}"


# ─── Quick smoke test (run as plain script) ───────────────────────────────────

if __name__ == "__main__":
    import sys

    GREEN = "\033[92m"
    RED   = "\033[91m"
    RESET = "\033[0m"
    BOLD  = "\033[1m"

    results = []

    def check(label, fn):
        try:
            fn()
            print(f"  {GREEN}✓{RESET} {label}")
            results.append((label, True, None))
        except Exception as e:
            print(f"  {RED}✗{RESET} {label}")
            print(f"      {RED}{e}{RESET}")
            results.append((label, False, str(e)))

    print(f"\n{BOLD}Data Engineer API smoke tests → {BASE_URL}{RESET}\n")

    # Server check
    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.ConnectionError:
        print(f"{RED}ERROR: Cannot connect to {BASE_URL}. Is the server running?{RESET}")
        sys.exit(1)

    print("── Connections ─────────────────────────────────────────────")
    check("GET /de/connections → 200 list",
          lambda: (lambda r: (
              r.status_code == 200 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}: {r.text}"))
          ))(get("/de/connections")))

    check("GET /de/connections/<fake_id> → 404",
          lambda: (lambda r: (
              r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}"))
          ))(get(f"/de/connections/{FAKE_UUID}")))

    check("DELETE /de/connections/<fake_id> → 404",
          lambda: (lambda r: (
              r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}"))
          ))(delete(f"/de/connections/{FAKE_UUID}")))

    check("POST /de/connections/<fake_id>/test → 404",
          lambda: (lambda r: (
              r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}"))
          ))(post(f"/de/connections/{FAKE_UUID}/test")))

    check("GET /de/connections/<fake_id>/schema → 404",
          lambda: (lambda r: (
              r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}"))
          ))(get(f"/de/connections/{FAKE_UUID}/schema")))

    print("\n── Raw Connection Test ──────────────────────────────────────")
    check("POST /de/connections/test (bad creds) → success=False",
          lambda: (lambda r: (
              r.status_code == 200 and r.json().get("success") is False
              or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}: {r.json()}"))
          ))(post("/de/connections/test", json={"host": "127.0.0.1", "port": 19999,
                                                "database": "x", "username": "x", "password": "x", "ssl": False})))

    check("POST /de/connections/test (connection_string) → success=False",
          lambda: (lambda r: (
              r.status_code == 200 and r.json().get("success") is False
              or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}: {r.json()}"))
          ))(post("/de/connections/test", json={"connection_string": "postgresql://x:x@127.0.0.1:19999/x"})))

    print("\n── Sessions ─────────────────────────────────────────────────")
    check("GET /de/sessions → 200 list",
          lambda: (lambda r: (
              r.status_code == 200 and isinstance(r.json(), list)
              or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}: {r.text}"))
          ))(get("/de/sessions")))

    check("GET /de/sessions/<fake_id> → 404",
          lambda: (lambda r: (
              r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}"))
          ))(get(f"/de/sessions/{FAKE_UUID}")))

    print("\n── Runs ─────────────────────────────────────────────────────")
    check("GET /de/runs/<fake_id> → 404",
          lambda: (lambda r: (
              r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}"))
          ))(get(f"/de/runs/{FAKE_UUID}")))

    print("\n── Ask ──────────────────────────────────────────────────────")
    check("POST /de/connections/<fake_id>/ask (no question) → 400",
          lambda: (lambda r: (
              r.status_code == 400 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}: {r.text}"))
          ))(post(f"/de/connections/{FAKE_UUID}/ask", json={})))

    check("POST /de/connections/<fake_id>/ask (valid question) → 404 (no conn)",
          lambda: (lambda r: (
              r.status_code == 404 or (_ for _ in ()).throw(AssertionError(f"Got {r.status_code}: {r.text}"))
          ))(post(f"/de/connections/{FAKE_UUID}/ask", json={"question": "How many rows?"})))

    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    failed = [(lbl, err) for lbl, ok, err in results if not ok]

    print(f"\n{'─' * 60}")
    if failed:
        print(f"{RED}{BOLD}FAILED: {len(failed)}/{total}{RESET}")
        for lbl, err in failed:
            print(f"  {RED}✗{RESET} {lbl}: {err}")
    else:
        print(f"{GREEN}{BOLD}ALL {total} CHECKS PASSED{RESET}")

    sys.exit(0 if not failed else 1)
