"""Публичный интерфейс кодека.

Контракт:
- encode(png_bytes, max_bytes) -> bytes (собственный формат, len <= max_bytes)
  или бросает CannotFit.
- decode(fmt_bytes) -> bytes (PNG 8 бит, W×H оригинала).
  Stateless, не требует оригинала.

API-слой не знает про внутренности кодека. Кодек не знает про HTTP.
"""

from .errors import BadInput, CannotFit, CorruptFormat
from .decoder import decode as _decoder_decode
from .encoder import encode as _encoder_encode

__all__ = ["encode", "decode", "BadInput", "CannotFit", "CorruptFormat"]


def encode(png_bytes: bytes, max_bytes: int) -> bytes:
    """Закодировать PNG в собственный формат.

    Гарантии: len(result) <= max_bytes, иначе CannotFit.
    Бросает BadInput на невалидный PNG или max_bytes <= 0.
    """
    return _encoder_encode(png_bytes, max_bytes)


def decode(fmt_bytes: bytes) -> bytes:
    """Декодировать байты собственного формата в PNG 8 бит.

    Гарантии: W×H совпадают с оригиналом. Stateless.
    Бросает CorruptFormat на битые данные.
    """
    return _decoder_decode(fmt_bytes)
