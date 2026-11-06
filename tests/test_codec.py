"""Контрактные тесты кодека.

Проверяют encode/decode по спецификации, а не детали реализации.
Фикстуры генерируются в тесте через Pillow — без бинарных файлов в репо.
"""

import io
import subprocess
import sys

import pytest
from PIL import Image

from codec import BadInput, CannotFit, CorruptFormat, decode, encode


def _make_png(width: int, height: int, mode: str = "RGB") -> bytes:
    """Сгенерить простой PNG в памяти без файлов в репо."""
    img = Image.new(mode, (width, height), color=(128, 64, 32) if mode == "RGB" else 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_encode_returns_bytes_within_max_bytes():
    png = _make_png(128, 128)
    out = encode(png, 8192)
    assert isinstance(out, bytes)
    assert 0 < len(out) <= 8192


def test_encode_512x512_fits_8kb():
    png = _make_png(512, 512)
    out = encode(png, 8192)
    assert len(out) <= 8192


def test_decode_returns_png_same_dimensions():
    png = _make_png(128, 96)
    fmt = encode(png, 8192)
    back = decode(fmt)
    assert back[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(io.BytesIO(back))
    assert img.size == (128, 96)
    assert img.mode == "RGB"


def test_decode_is_stateless():
    """decode должен работать в чистом процессе без encode."""
    png = _make_png(64, 64)
    fmt = encode(png, 8192)
    code = (
        "import sys; from codec import decode; "
        "png = decode(sys.stdin.buffer.read()); "
        "sys.stdout.buffer.write(png)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        input=fmt,
        capture_output=True,
        check=True,
    )
    assert result.stdout[:8] == b"\x89PNG\r\n\x1a\n"


def test_encode_invalid_png_raises_badinput():
    with pytest.raises(BadInput):
        encode(b"", 100)
    with pytest.raises(BadInput):
        encode(b"not a png", 100)


def test_encode_nonpositive_max_bytes_raises_badinput():
    png = _make_png(32, 32)
    with pytest.raises(BadInput):
        encode(png, 0)


def test_decode_garbage_raises_corruptformat():
    with pytest.raises(CorruptFormat):
        decode(b"")
    with pytest.raises(CorruptFormat):
        decode(b"totally garbage bytes")


def test_encode_1x1():
    png = _make_png(1, 1)
    fmt = encode(png, 8192)
    assert len(fmt) <= 8192
    img = Image.open(io.BytesIO(decode(fmt)))
    assert img.size == (1, 1)


def test_encode_rgba():
    png = _make_png(64, 64, mode="RGBA")
    fmt = encode(png, 8192)
    img = Image.open(io.BytesIO(decode(fmt)))
    assert img.size == (64, 64)


def test_encode_deterministic():
    png = _make_png(64, 64)
    assert encode(png, 8192) == encode(png, 8192)