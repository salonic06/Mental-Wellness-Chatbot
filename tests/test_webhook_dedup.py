"""Tests for Meta webhook message-id deduplication."""

from webhook_dedup import try_claim_message


def test_try_claim_message_first_time(tmp_db):
    assert try_claim_message("wamid.abc123") is True


def test_try_claim_message_duplicate(tmp_db):
    assert try_claim_message("wamid.dup456") is True
    assert try_claim_message("wamid.dup456") is False


def test_try_claim_empty_id_always_processes(tmp_db):
    assert try_claim_message("") is True
    assert try_claim_message("") is True
