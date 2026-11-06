"""Декодер: байты собственного формата -> PNG 8 бит.

Зона ответственности: разработчик алгоритма (codec/).

TODO: реализовать decode(fmt_bytes) -> bytes, stateless, без оригинала.
"""


def parse_header(data: bytes):
    """Распарсить заголовок формата (заглушка)."""
    return None
