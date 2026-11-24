import json
import pathlib
import re
from datetime import UTC, datetime, timedelta

from jsonschema import Draft202012Validator

SCHEMA = json.loads((pathlib.Path(__file__).parents[2] / "contracts/transfer_card.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=Draft202012Validator.FORMAT_CHECKER)
CARD_FIELDS = {"id", "itemCode", "fromBranch", "toBranch", "quantity", "priority", "status", "requestedAt"}
FIXED_NOW = datetime(2026, 11, 3, 9, 30, tzinfo=UTC)


def request_transfer(client):
    return client.post("/v1/transfers", json={"itemCode": "MET500", "fromBranch": "heliopolis",
                                              "toBranch": "tanta", "quantity": 20})


def test_pending_card_matches_schema(client):
    r = request_transfer(client)
    assert r.status_code == 201
    card = r.json()
    VALIDATOR.validate(card)
    assert set(card) == CARD_FIELDS


def test_approved_card_matches_schema(client):
    transfer_id = request_transfer(client).json()["id"]
    r = client.post(f"/v1/transfers/{transfer_id}/approve")
    assert r.status_code == 200
    card = r.json()
    VALIDATOR.validate(card)
    assert set(card) == CARD_FIELDS


def test_inbox_cards_match_schema(client):
    request_transfer(client)
    transfer_id = request_transfer(client).json()["id"]
    assert client.post(f"/v1/transfers/{transfer_id}/approve").status_code == 200
    items = client.get("/v1/branches/tanta/transfers").json()["items"]
    assert len(items) == 2
    for card in items:
        VALIDATOR.validate(card)
        assert set(card) == CARD_FIELDS


def test_requested_at_is_utc_iso_with_z(client):
    requested_at = request_transfer(client).json()["requestedAt"]
    assert requested_at.endswith("Z")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", requested_at)
    parsed = datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)
    assert parsed == FIXED_NOW


def test_card_has_exactly_the_contract_fields(client):
    assert set(request_transfer(client).json()) == CARD_FIELDS
