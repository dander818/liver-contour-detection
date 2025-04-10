#!/bin/bash

# Подождать, если нужно для подключения к базе данных
# (в текущей версии используется SQLite)

echo "Apply database migrations"
python manage.py migrate

echo "Collect static files"
python manage.py collectstatic --noinput

echo "Starting server"
exec gunicorn liver_detection.wsgi:application --bind 0.0.0.0:8000 