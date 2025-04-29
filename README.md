# Система распознавания контуров печени

Веб-приложение для загрузки медицинских снимков и автоматического распознавания контуров печени.

## Запуск с использованием Docker

Для запуска приложения через Docker выполните следующие шаги:

1. Убедитесь, что у вас установлены Docker и Docker Compose

2. Клонируйте репозиторий:
```
git clone <ссылка на репозиторий>
cd liver_contour_detection
```

3. Запустите приложение:
```
docker-compose up -d
```

4. Приложение будет доступно по адресу http://localhost:8000

## Создание суперпользователя

Для создания суперпользователя (администратора) выполните:

```
docker-compose exec web python manage.py createsuperuser
```

## Управление контейнером

- Просмотр логов: `docker-compose logs -f`
- Остановка контейнера: `docker-compose down`
- Перезапуск: `docker-compose restart`

## Резервное копирование данных

База данных и медиа-файлы сохраняются на хосте в директориях:
- База данных: внутри контейнера `/app/db.sqlite3`
- Медиа-файлы: `./media`

## Деплой на PythonAnywhere

Для деплоя приложения на PythonAnywhere:

1. Зарегистрируйтесь на [PythonAnywhere](https://www.pythonanywhere.com/) (бесплатный аккаунт подойдет)

2. Загрузите код на PythonAnywhere:
   - Через Bash консоль PythonAnywhere:
     ```bash
     git clone https://github.com/ваш_пользователь/liver-contour-detection.git
     ```
   - Или загрузите zip-архив через раздел Files

3. Создайте виртуальное окружение и установите зависимости:
   ```bash
   cd liver-contour-detection
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. Настройте веб-приложение:
   - Перейдите в раздел "Web" на PythonAnywhere
   - Нажмите "Add a new web app"
   - Выберите ручную настройку с Python (Manual configuration -> Python 3.9)
   - В поле "Source code" укажите путь к вашему проекту: `/home/ваш_пользователь/liver-contour-detection`
   - В поле "Working directory" укажите тот же путь
   - В разделе "WSGI configuration file" отредактируйте файл:
     - Удалите стандартный код
     - Вставьте содержимое из файла `wsgi_pythonanywhere.py` (замените YOURUSERNAME вашим именем пользователя)

5. Настройте статические файлы:
   - В разделе "Static files" добавьте:
     - URL: `/static/` -> Directory: `/home/ваш_пользователь/liver-contour-detection/static`
     - URL: `/media/` -> Directory: `/home/ваш_пользователь/liver-contour-detection/media`

6. Создайте директории для статических и медиа-файлов:
   ```bash
   mkdir -p static media
   ```

7. Примените миграции и создайте суперпользователя:
   ```bash
   python manage.py migrate
   python manage.py collectstatic
   python manage.py createsuperuser
   ```

8. Перезапустите веб-приложение, нажав на кнопку "Reload" в разделе Web

Ваш сайт будет доступен по адресу: https://ваш_пользователь.pythonanywhere.com

PythonAnywhere предоставляет:
- Бесплатное размещение одного веб-приложения
- 512 МБ дискового пространства
- Доступ к консоли Python
- Поддержку Django и других фреймворков
- Удобный файловый менеджер

## Развитие проекта

В будущем планируется добавить:
- Функциональность автоматического распознавания контуров печени
- Возможность экспорта результатов в различных форматах
- Администраторский интерфейс для управления пользователями 