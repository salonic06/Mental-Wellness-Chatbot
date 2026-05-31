"""Isolated SQLite DB for each test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import db_paths
from database import init_db


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_wellness.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))
    db_paths.DATABASE_PATH = Path(db_file)

    import state_store

    state_store._DB = str(db_file)

    init_db(str(db_file))
    yield db_file


@pytest.fixture(autouse=True)
def reset_bot_singleton():
    import bot_router

    bot_router._bot_instance = None
    yield
    bot_router._bot_instance = None


@pytest.fixture()
def bot(tmp_db):
    from wellness_bot_class import WellnessBot

    return WellnessBot()


@pytest.fixture()
def user_phone():
    return "919900000099"
