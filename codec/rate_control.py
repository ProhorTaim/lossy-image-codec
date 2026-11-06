"""Контроль скорости: подбор q_scale и downscale_ratio под max_bytes.

Стратегия:
  1. Перебираем downscale_ratio = 1, 2, 4.
  2. Для каждого — бинарный поиск по q_scale (от 1 вверх), ищем минимальный
     q_scale, при котором результат влезает в max_bytes.
  3. Если при максимальном q_scale не влезает — следующий downscale_ratio.
  4. Если ни один вариант не подошел — CannotFit.

Каждый шаг проверяет len(result) <= max_bytes.
"""

from .encoder import MODE_RGB, MODE_YCBCR_420, _encode_full
from .errors import BadInput, CannotFit

_MAX_Q = 5000          # верхняя граница q_scale (чем больше, тем сильнее сжатие)
_MAX_Q_ITER = 12       # максимум итераций бинарного поиска


def _try_params(png_bytes: bytes, max_bytes: int, downscale_ratio: int,
                mode: int) -> bytes | None:
    """Бинарный поиск по q_scale для фиксированного downscale_ratio и mode.

    Возвращает лучшее (наименьшее q_scale) вкладывающееся в max_bytes кодирование,
    или None если даже максимальный q_scale не помогает.
    """
    # Расширяем верхнюю границу, пока не влезет или не упремся в _MAX_Q
    high = 1
    while high <= _MAX_Q:
        result = _encode_full(png_bytes, high, downscale_ratio, mode)
        if len(result) <= max_bytes:
            break
        high *= 2

    if high > _MAX_Q:
        # Пробуем максимальный q_scale ещё раз
        result = _encode_full(png_bytes, _MAX_Q, downscale_ratio, mode)
        if len(result) <= max_bytes:
            high = _MAX_Q
        else:
            return None

    high = min(high, _MAX_Q)

    # Бинарный поиск наименьшего q_scale, который влезает (лучшее качество)
    lo, hi = 1, high
    best_q = hi
    iters = 0
    while lo <= hi and iters < _MAX_Q_ITER:
        mid = (lo + hi) // 2
        result = _encode_full(png_bytes, mid, downscale_ratio, mode)
        if len(result) <= max_bytes:
            best_q = mid
            hi = mid - 1
        else:
            lo = mid + 1
        iters += 1

    result = _encode_full(png_bytes, best_q, downscale_ratio, mode)
    if len(result) <= max_bytes:
        return result
    return None


def encode(png_bytes: bytes, max_bytes: int) -> bytes:
    """Подобрать параметры под max_bytes и вернуть байты PIC1.

    Порядок проб:
      1. YCbCr 4:2:0, downscale=1
      2. YCbCr 4:2:0, downscale=2
      3. YCbCr 4:2:0, downscale=4
      4. RGB (без chroma subsampling), downscale=1 — для крошечных/графических
         картинок где YCbCr избыточен.

    Бросает BadInput при max_bytes <= 0.
    Бросает CannotFit если ни один вариант не влез.
    """
    if max_bytes <= 0:
        raise BadInput("max_bytes must be positive")

    candidates = [
        (MODE_YCBCR_420, 1),
        (MODE_YCBCR_420, 2),
        (MODE_YCBCR_420, 4),
        (MODE_RGB, 1),
    ]

    for mode, downscale_ratio in candidates:
        result = _try_params(png_bytes, max_bytes, downscale_ratio, mode)
        if result is not None:
            return result

    raise CannotFit(f"cannot fit in {max_bytes} bytes")
