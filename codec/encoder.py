"""Энкодер: PNG -> байты собственного формата.

Зона ответственности: разработчик алгоритма (codec/).

TODO: реализовать encode(png_bytes, max_bytes) -> bytes с уложением в лимит.
"""


def encode_header(width: int, height: int) -> bytes:
    """Сформировать заголовок формата (заглушка)."""
    return b""
