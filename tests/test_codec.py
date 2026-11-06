"""Тесты для codec/ (заглушка).

Зона ответственности: QA (tests/).
"""

import pytest


def test_codec_importable():
    """Smoke-тест: модуль кодека импортируется без ошибок."""
    import codec  # noqa: F401


def test_encode_not_implemented():
    """encode пока не реализован — бросает NotImplementedError."""
    from codec import encode
    with pytest.raises(NotImplementedError):
        encode(b"", 100)


def test_decode_not_implemented():
    """decode пока не реализован — бросает NotImplementedError."""
    from codec import decode
    with pytest.raises(NotImplementedError):
        decode(b"")
