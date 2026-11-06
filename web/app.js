// app.js — клиентская логика UI (заглушка).
//
// TODO: реализовать:
//   - отправку PNG на POST /v1/encode?max_bytes=N
//   - получение байтов формата и декодирование через POST /v1/decode
//   - отображение оригинала и восстановленного изображения
//   - слайдер сравнения

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("upload-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    console.log("TODO: реализовать логику сжатия через HTTP API");
  });
});
