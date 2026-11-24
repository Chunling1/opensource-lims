"""Opt-in pytest fixtures for module tests.

Use ``pytest_plugins = (\"testkit.fixtures\",)`` in a test module.  Fixtures
are opt-in so legacy suites can migrate gradually without fixture-name clashes.
"""

from __future__ import annotations

import pytest

from app.extensions import db

from .app import assert_isolated_app, create_isolated_app
from .factories import ScenarioFactory


@pytest.fixture()
def isolated_app(tmp_path):
    app = create_isolated_app(tmp_path)
    yield app
    # Re-check immediately before teardown: a test must not have rebound the
    # shared SQLAlchemy engine or storage root to an external location.
    assert_isolated_app(app, tmp_path)
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def isolated_client(isolated_app):
    return isolated_app.test_client()


@pytest.fixture()
def scenario_factory(isolated_app):
    with isolated_app.app_context():
        yield ScenarioFactory()
        db.session.rollback()


__all__ = ["isolated_app", "isolated_client", "scenario_factory"]
