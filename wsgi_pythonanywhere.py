"""
WSGI файл для PythonAnywhere
Этот файл используется в настройках веб-приложения PythonAnywhere
"""

import os
import sys

# Добавьте путь к вашему проекту Django
path = '/home/YOURUSERNAME/liver-contour-detection'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'liver_detection.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application() 