"""Тесты для api/ (заглушка).

Зона ответственности: QA (tests/).
"""

import pytest


def test_api_importable():
    """Smoke-тест: модуль api импортируется без ошибок."""
    import api  # noqa: F401


def test_create_app_returns_none_stub():
    """create_app пока возвращает None (заглушка)."""
    from api.main import create_app
    assert create_app() is None
