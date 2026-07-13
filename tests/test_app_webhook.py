import hashlib
import hmac
import json
import os

from fastapi.testclient import TestClient

from app import app


def _signed_post(client, body: bytes, secret: str):
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhook",
        content=body,
        headers={"X-Hub-Signature-256": f"sha256={sig}"},
    )


def test_webhook_verify():
    os.environ["META_VERIFY_TOKEN"] = "test-token"
    client = TestClient(app)
    r = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-token",
            "hub.challenge": "abc123",
        },
    )
    assert r.status_code == 200
    assert r.text == "abc123"


def test_webhook_ignores_non_message(tmp_db, monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("META_VERIFY_TOKEN", "test-token")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "fake")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123")
    monkeypatch.setattr(
        "app.verify_meta_signature",
        lambda **kwargs: True,
    )
    client = TestClient(app)
    payload = {"entry": []}
    body = json.dumps(payload).encode()
    r = _signed_post(client, body, "secret")
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"


def _text_message_payload(message_id: str = "wamid.TEST123") -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "919900000099",
                                    "id": message_id,
                                    "type": "text",
                                    "text": {"body": "hello"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def test_webhook_dedup_duplicate_delivery(tmp_db, monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setattr("app.verify_meta_signature", lambda **kwargs: True)
    monkeypatch.setattr("app._process_inbound_and_reply", lambda *args: None)
    client = TestClient(app)
    body = json.dumps(_text_message_payload("wamid.DUP999")).encode()
    r1 = _signed_post(client, body, "secret")
    r2 = _signed_post(client, body, "secret")
    assert r1.status_code == 200
    assert r1.json()["status"] == "ok"
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"

