class CodecError(Exception):
    """Базовая ошибка кодека."""


class BadInput(CodecError):
    """Входные данные не являются валидным PNG или max_bytes некорректен."""


class CannotFit(CodecError):
    """Невозможно уложиться в max_bytes даже при максимальном сжатии."""


class CorruptFormat(CodecError):
    """Битые или несовместимые байты собственного формата."""
