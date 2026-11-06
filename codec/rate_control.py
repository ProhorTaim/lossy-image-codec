"""Контроль скорости (rate control): подбор параметров под max_bytes.

Зона ответственности: разработчик алгоритма (codec/).

TODO: реализовать подбор качества/квантования так, чтобы len <= max_bytes,
       иначе CannotFit.
"""


def choose_quality(max_bytes: int, estimated_size: int) -> float:
    """Выбрать целевое качество (заглушка)."""
    return 1.0
