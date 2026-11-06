"""Формат ошибок по спецификации:
{"error": {"code": "...", "message": "..."}}
"""


class APIError(Exception):
    """Ошибка API с кодом и HTTP-статусом."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}
