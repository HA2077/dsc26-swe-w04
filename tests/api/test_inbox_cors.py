from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from nour_transfers.app import create_app

ALLOWED_ORIGINS = ["https://branch.nour.example", "http://localhost:5173"]
EVIL_ORIGIN = "https://evil.example"
FIXED_NOW = datetime(2026, 11, 3, 9, 30, tzinfo=UTC)


@pytest.fixture
def ordering_client():
    app = create_app(
        stock={("a", "X"): 100, ("b", "X"): 10,
               ("a", "Y"): 100, ("b", "Y"): 10,
               ("a", "Z"): 100, ("b", "Z"): 10},
        items={"X": {"chronic": True, "reserve": 0},
               "Y": {"chronic": False, "reserve": 0},
               "Z": {"chronic": False, "reserve": 0}},
        sales={("b", "X"): 5.0, ("b", "Y"): 2.0},
        now=lambda: FIXED_NOW,
    )
    return TestClient(app)


def request_transfer(client, item="X", source="a", target="b", quantity=5):
    return client.post("/v1/transfers", json={"itemCode": item, "fromBranch": source,
                                              "toBranch": target, "quantity": quantity})


def test_inbox_sorts_by_priority_then_request_order(ordering_client):
    for item in ["X", "Y", "Z", "X"]:
        assert request_transfer(ordering_client, item=item).status_code == 201
    items = ordering_client.get("/v1/branches/b/transfers").json()["items"]
    assert [card["id"] for card in items] == ["tr_1", "tr_4", "tr_2", "tr_3"]
    assert [card["priority"] for card in items] == ["urgent", "urgent", "high", "normal"]


def test_inbox_includes_pending_and_approved(ordering_client):
    first = request_transfer(ordering_client, item="X").json()["id"]
    request_transfer(ordering_client, item="Y")
    assert ordering_client.post(f"/v1/transfers/{first}/approve").status_code == 200
    items = ordering_client.get("/v1/branches/b/transfers").json()["items"]
    assert len(items) == 2
    assert {card["status"] for card in items} == {"pending", "approved"}
    assert next(card for card in items if card["id"] == first)["status"] == "approved"


def test_inbox_only_contains_transfers_to_that_branch(client):
    request_transfer(client, item="MET500", source="heliopolis", target="tanta", quantity=20)
    assert len(client.get("/v1/branches/tanta/transfers").json()["items"]) == 1
    assert client.get("/v1/branches/heliopolis/transfers").json()["items"] == []


def test_inbox_for_unknown_branch_is_empty(client):
    r = client.get("/v1/branches/giza/transfers")
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_stock_endpoint_returns_current_units(client):
    r = client.get("/v1/branches/heliopolis/stock/MET500")
    assert r.status_code == 200
    assert r.json() == {"branch": "heliopolis", "itemCode": "MET500", "units": 40}


def test_stock_endpoint_returns_zero_for_unknown_branch_or_item(client):
    unknown_branch = client.get("/v1/branches/giza/stock/MET500").json()
    assert unknown_branch["units"] == 0
    assert unknown_branch["branch"] == "giza"
    unknown_item = client.get("/v1/branches/heliopolis/stock/NOT_A_DRUG").json()
    assert unknown_item["units"] == 0
    assert unknown_item["itemCode"] == "NOT_A_DRUG"


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_preflight_allows_known_origin(client, origin):
    r = client.options("/v1/transfers", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization",
    })
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_rejects_unknown_origin(client):
    r = client.options("/v1/transfers", headers={
        "Origin": EVIL_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization",
    })
    assert r.status_code == 400
    assert r.headers.get("access-control-allow-origin") is None


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_simple_request_allows_known_origin(client, origin):
    r = client.get("/v1/branches/tanta/stock/MET500", headers={"Origin": origin})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == origin
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_cors_simple_request_has_no_header_for_unknown_origin(client):
    r = client.get("/v1/branches/tanta/stock/MET500", headers={"Origin": EVIL_ORIGIN})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") is None
