FROM python:3.9-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем файлы проекта
COPY . .

# Создаем директории для статических и медиа-файлов
RUN mkdir -p static media

# Expose порт
EXPOSE 8000

# Делаем entrypoint.sh исполняемым
RUN chmod +x entrypoint.sh

# Запускаем сервер через entrypoint
ENTRYPOINT ["/app/entrypoint.sh"] 