import pytest

PROBLEM = "application/problem+json"
CARD_FIELDS = {"id", "itemCode", "fromBranch", "toBranch", "quantity", "priority", "status", "requestedAt"}


def assert_problem(response, status, slug):
    assert response.status_code == status
    assert response.headers["content-type"].startswith(PROBLEM)
    body = response.json()
    assert body["type"] == f"/problems/{slug}"
    assert body["status"] == status
    assert body["title"]


def stock(client, branch, item_code):
    return client.get(f"/v1/branches/{branch}/stock/{item_code}").json()["units"]


def request_transfer(client, item="MET500", source="heliopolis", target="tanta", quantity=20):
    return client.post("/v1/transfers", json={"itemCode": item, "fromBranch": source,
                                              "toBranch": target, "quantity": quantity})


def test_request_returns_a_pending_card(client):
    r = request_transfer(client)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == CARD_FIELDS
    assert body["id"] == "tr_1"
    assert body["itemCode"] == "MET500"
    assert body["fromBranch"] == "heliopolis"
    assert body["toBranch"] == "tanta"
    assert body["quantity"] == 20
    assert body["priority"] == "urgent"
    assert body["status"] == "pending"


def test_priority_comes_from_the_destination_branch(client):
    metformin = request_transfer(client, item="MET500", quantity=20)
    amoxicillin = request_transfer(client, item="AMOX250", quantity=5)
    assert metformin.json()["priority"] == "urgent"
    assert amoxicillin.json()["priority"] == "high"


def test_request_does_not_move_stock(client):
    request_transfer(client, quantity=20)
    assert stock(client, "heliopolis", "MET500") == 40
    assert stock(client, "tanta", "MET500") == 2


def test_ids_are_sequential_in_request_order(client):
    first = request_transfer(client, item="MET500", quantity=20)
    second = request_transfer(client, item="AMOX250", quantity=5)
    assert first.json()["id"] == "tr_1"
    assert second.json()["id"] == "tr_2"


def test_unknown_extra_fields_are_ignored(client):
    r = client.post("/v1/transfers", json={"itemCode": "MET500", "fromBranch": "heliopolis",
                                           "toBranch": "tanta", "quantity": 20, "note": "urgent please"})
    assert r.status_code == 201


@pytest.mark.parametrize("body", [
    {"fromBranch": "heliopolis", "toBranch": "tanta", "quantity": 20},
    {"itemCode": "MET500", "fromBranch": "heliopolis", "toBranch": "tanta", "quantity": 0},
    {"itemCode": "MET500", "fromBranch": "heliopolis", "toBranch": "tanta", "quantity": "many"},
])
def test_invalid_body_is_a_validation_problem(client, body):
    r = client.post("/v1/transfers", json=body)
    assert_problem(r, 422, "validation")
    errors = r.json()["errors"]
    assert isinstance(errors, list) and errors
    assert all({"loc", "msg"} <= set(e) for e in errors)


def test_validation_runs_before_unknown_item(client):
    r = request_transfer(client, item="NOT_A_DRUG", quantity=0)
    assert_problem(r, 422, "validation")


def test_unknown_item_is_404(client):
    assert_problem(request_transfer(client, item="NOT_A_DRUG"), 404, "unknown-item")


def test_unknown_branch_is_404(client):
    assert_problem(request_transfer(client, target="giza"), 404, "unknown-branch")


def test_same_branch_is_422(client):
    assert_problem(request_transfer(client, source="heliopolis", target="heliopolis"), 422, "same-branch")


def test_below_reserve_is_409(client):
    assert_problem(request_transfer(client, quantity=31), 409, "below-reserve")


def test_approve_moves_stock_from_source_to_destination_once(client):
    transfer_id = request_transfer(client, quantity=20).json()["id"]
    r = client.post(f"/v1/transfers/{transfer_id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
    assert stock(client, "heliopolis", "MET500") == 20
    assert stock(client, "tanta", "MET500") == 22


def test_approving_twice_is_refused(client):
    transfer_id = request_transfer(client, quantity=20).json()["id"]
    assert client.post(f"/v1/transfers/{transfer_id}/approve").status_code == 200
    r = client.post(f"/v1/transfers/{transfer_id}/approve")
    assert_problem(r, 409, "not-pending")
    assert stock(client, "heliopolis", "MET500") == 20
    assert stock(client, "tanta", "MET500") == 22


def test_approving_unknown_transfer_is_404(client):
    assert_problem(client.post("/v1/transfers/tr_999/approve"), 404, "unknown-transfer")


def test_approve_fails_when_stock_changed_since_request(client):
    large = request_transfer(client, quantity=30).json()["id"]
    smaller = request_transfer(client, quantity=20).json()["id"]
    assert client.post(f"/v1/transfers/{smaller}/approve").status_code == 200
    r = client.post(f"/v1/transfers/{large}/approve")
    assert_problem(r, 409, "below-reserve")
    assert stock(client, "heliopolis", "MET500") == 20
    assert stock(client, "tanta", "MET500") == 22


@pytest.mark.parametrize("path,body,status,slug", [
    ("/v1/transfers", {"itemCode": "NOT_A_DRUG", "fromBranch": "heliopolis", "toBranch": "tanta",
                       "quantity": 1}, 404, "unknown-item"),
    ("/v1/transfers", {"itemCode": "MET500", "fromBranch": "heliopolis", "toBranch": "heliopolis",
                       "quantity": 1}, 422, "same-branch"),
    ("/v1/transfers", {"itemCode": "MET500", "fromBranch": "heliopolis", "toBranch": "tanta",
                       "quantity": 31}, 409, "below-reserve"),
    ("/v1/transfers", {}, 422, "validation"),
    ("/v1/transfers/tr_999/approve", None, 404, "unknown-transfer"),
])
def test_every_error_is_a_problem_json(client, path, body, status, slug):
    r = client.post(path, json=body) if body is not None else client.post(path)
    assert_problem(r, status, slug)
