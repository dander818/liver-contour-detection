from django.db import models
from django.contrib.auth.models import User
import os

def user_directory_path(instance, filename):
    # Файлы будут загружаться в директорию MEDIA_ROOT/user_<id>/<filename>
    return f'user_{instance.user.id}/{filename}'

class Image(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='images')
    # Оригинальный файл (DCM или другой)
    image = models.FileField(upload_to=user_directory_path)
    # Обработанный файл (PNG)
    processed_image = models.FileField(upload_to=user_directory_path, null=True, blank=True)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.original_filename} ({self.user.username})"
    
    def save(self, *args, **kwargs):
        # Сохраняем оригинальное имя файла только при первой загрузке
        if not self.pk and not self.original_filename and self.image:
             self.original_filename = os.path.basename(self.image.name)
        super().save(*args, **kwargs)
