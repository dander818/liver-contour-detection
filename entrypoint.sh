#!/bin/bash

set -e
set -o pipefail

echo "Starting entrypoint script..."

# Создание необходимых директорий
mkdir -p /app/static /app/media /app/images/migrations /app/users/migrations
echo "Directories checked"

# Установка правильных прав для директорий миграций
chmod -R 777 /app/images/migrations /app/users/migrations
echo "Permissions set for migrations directories"

# Применение миграций базы данных
echo "Applying database migrations..."
python manage.py migrate --noinput || { echo "Migration failed"; exit 1; }
echo "Migrations completed"

# Сбор статических файлов
echo "Collecting static files..."
python manage.py collectstatic --noinput || { echo "Collectstatic failed"; exit 1; }
echo "Static files collected"

# Установка прав на файл базы данных
if [ -f /app/db.sqlite3 ]; then
    chmod 666 /app/db.sqlite3
    echo "Database file permissions updated"
fi

# Запуск сервера Gunicorn
echo "Starting Gunicorn server..."
exec gunicorn liver_detection.wsgi:application --bind 0.0.0.0:8000 