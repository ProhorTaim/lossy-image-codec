"""HTTP-сервис по спецификации openapi.yaml.

TODO: реализовать GET /v1/health, POST /v1/encode, POST /v1/decode.
      На этом этапе — заглушка с комментариями, как это должно работать.
"""


def create_app():
    """Создать WSGI/ASGI приложение (заглушка).

    Возвращает объект приложения, который позднее будет обслуживать:
      - GET  /v1/health          -> 200 {"status":"ok"}
      - POST /v1/encode?max_bytes=N (image/png) -> application/octet-stream
      - POST /v1/decode (application/octet-stream) -> image/png
    """
    return None
