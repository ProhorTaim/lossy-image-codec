"""Публичный интерфейс кодека.

Контракт:
- encode(png_bytes, max_bytes) -> bytes (собственный формат, len <= max_bytes)
  или бросает CannotFit.
- decode(fmt_bytes) -> bytes (PNG 8 бит, W×H оригинала).
  Stateless, не требует оригинала.

API-слой не знает про внутренности кодека. Кодек не знает про HTTP.
"""

from .errors import BadInput, CannotFit, CorruptFormat

__all__ = ["encode", "decode", "BadInput", "CannotFit", "CorruptFormat"]


def encode(png_bytes: bytes, max_bytes: int) -> bytes:
    """Закодировать PNG в собственный формат.

    Гарантии: len(result) <= max_bytes, иначе CannotFit.
    Бросает BadInput на невалидный PNG или max_bytes <= 0.
    """
    raise NotImplementedError("encoder not implemented yet")


def decode(fmt_bytes: bytes) -> bytes:
    """Декодировать байты собственного формата в PNG 8 бит.

    Гарантии: W×H совпадают с оригиналом. Stateless.
    Бросает CorruptFormat на битые данные.
    """
    raise NotImplementedError("decoder not implemented yet")
