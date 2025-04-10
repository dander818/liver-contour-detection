#!/bin/bash

set -e
set -o pipefail

echo "Starting entrypoint script..."

# Создание необходимых директорий
mkdir -p /app/static /app/media
echo "Directories checked"

# Применение миграций базы данных
echo "Applying database migrations..."
python manage.py migrate --noinput || { echo "Migration failed"; exit 1; }
echo "Migrations completed"

# Сбор статических файлов
echo "Collecting static files..."
python manage.py collectstatic --noinput || { echo "Collectstatic failed"; exit 1; }
echo "Static files collected"

# Запуск сервера Gunicorn
echo "Starting Gunicorn server..."
exec gunicorn liver_detection.wsgi:application --bind 0.0.0.0:8000 