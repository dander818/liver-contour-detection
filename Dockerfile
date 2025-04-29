FROM python:3.9.6

WORKDIR /app

# Устанавливаем системные зависимости для Pillow
RUN apt-get update && apt-get install -y libjpeg-dev zlib1g-dev --no-install-recommends && rm -rf /var/lib/apt/lists/*

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