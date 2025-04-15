from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseBadRequest
from .forms import ImageUploadForm
from .models import Image
from .utils import dcm_to_png  # Импортируем нашу утилиту
import os

# Create your views here.

@login_required
def original_image_list(request):
    """Отображает список оригинальных (необработанных) изображений."""
    # Фильтруем изображения, чтобы показать только те, что НЕ обработаны ИЛИ у которых ЕСТЬ оригинальный файл
    # (на случай, если обработка не удалась, но файл остался)
    images = Image.objects.filter(user=request.user).order_by('-uploaded_at')
    context = {
        'images': images,
        'title': "Оригинальные изображения",
        'list_type': 'original'
    }
    return render(request, 'images/generic_image_list.html', context)

@login_required
def processed_image_list(request):
    """Отображает список обработанных изображений."""
    images = Image.objects.filter(user=request.user, processed=True, processed_image__isnull=False).order_by('-uploaded_at')
    context = {
        'images': images,
        'title': "Обработанные изображения",
        'list_type': 'processed'
    }
    return render(request, 'images/generic_image_list.html', context)

@login_required
def image_upload(request):
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.user = request.user
            image.original_filename = request.FILES['image'].name
            image.save()
            messages.success(request, 'Изображение успешно загружено!')
            return redirect('image_list')
    else:
        form = ImageUploadForm()
    return render(request, 'images/image_upload.html', {'form': form})

@login_required
def image_detail(request, image_id):
    image = get_object_or_404(Image, id=image_id, user=request.user)
    return render(request, 'images/image_detail.html', {'image': image})

@login_required
def image_delete(request, image_id):
    image = get_object_or_404(Image, id=image_id, user=request.user)
    if request.method == 'POST':
        # Удаляем файл с сервера, если он существует
        if image.image and os.path.isfile(image.image.path):
            os.remove(image.image.path)
        image.delete()
        messages.success(request, 'Изображение успешно удалено!')
        return redirect('image_list')
    return render(request, 'images/image_confirm_delete.html', {'image': image})

@login_required
def process_image(request, image_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Only POST requests are allowed")

    image_instance = get_object_or_404(Image, id=image_id, user=request.user)
    
    if image_instance.processed:
        messages.warning(request, "Это изображение уже было обработано.")
        return redirect('image_detail', image_id=image_id)
        
    if not image_instance.image or not os.path.exists(image_instance.image.path):
        messages.error(request, "Исходный файл изображения не найден.")
        return redirect('image_detail', image_id=image_id)
        
    original_path = image_instance.image.path
    
    # Создаем путь для PNG файла в той же директории пользователя
    # Используем то же имя файла, но с расширением .png
    base_filename = os.path.splitext(os.path.basename(image_instance.image.name))[0]
    png_filename = f"{base_filename}_processed.png"
    # Определяем директорию пользователя относительно MEDIA_ROOT
    user_dir = os.path.dirname(image_instance.image.name)
    # Полный путь для сохранения на диске
    png_save_path = os.path.join(settings.MEDIA_ROOT, user_dir, png_filename)
    # Путь для сохранения в модели (относительно MEDIA_ROOT)
    png_model_path = os.path.join(user_dir, png_filename)

    # Создаем директорию, если она не существует
    os.makedirs(os.path.dirname(png_save_path), exist_ok=True)
    
    # Конвертируем DCM в PNG
    converted_png_path = dcm_to_png(original_path, png_save_path)
    
    if converted_png_path:
        # Обновляем запись в БД
        image_instance.processed_image.name = png_model_path # Сохраняем путь к PNG
        image_instance.processed = True
        image_instance.save()
        messages.success(request, f"Изображение успешно преобразовано в PNG: {png_filename}")
    else:
        messages.error(request, "Ошибка при преобразовании изображения.")
        
    return redirect('image_detail', image_id=image_id)
