FROM python:3.9.6

WORKDIR /app

# Устанавливаем системные зависимости для Pillow, OpenCV, matplotlib и других библиотек
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libfreetype6-dev \
    pkg-config \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директории для статических и медиа-файлов с правильными правами доступа
RUN mkdir -p static media
RUN chmod -R 777 media

# Копируем файлы проекта (кроме volumes)
COPY . .

# Указываем matplotlib использовать Agg бэкенд (не-интерактивный)
ENV MPLBACKEND="Agg"

# Expose порт
EXPOSE 8000

# Делаем entrypoint.sh исполняемым
RUN chmod +x entrypoint.sh

# Запускаем сервер через entrypoint
ENTRYPOINT ["/app/entrypoint.sh"] 