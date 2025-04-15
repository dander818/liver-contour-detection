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
def image_list(request):
    images = Image.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'images/image_list.html', {'images': images})

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

    image = get_object_or_404(Image, id=image_id, user=request.user)
    
    # Проверяем, что файл существует
    if not image.image or not os.path.exists(image.image.path):
        messages.error(request, "Исходный файл изображения не найден.")
        return redirect('image_detail', image_id=image_id)
        
    dcm_path = image.image.path
    
    # Создаем путь для PNG файла в той же директории
    png_filename = os.path.splitext(os.path.basename(dcm_path))[0] + ".png"
    png_path = os.path.join(os.path.dirname(dcm_path), png_filename)
    
    # Конвертируем DCM в PNG
    converted_png_path = dcm_to_png(dcm_path, png_path)
    
    if converted_png_path:
        # Обновляем ссылку на файл в модели Image
        # Вычисляем относительный путь от MEDIA_ROOT
        relative_png_path = os.path.relpath(converted_png_path, settings.MEDIA_ROOT)
        image.image.name = relative_png_path # Обновляем поле ImageField
        image.original_filename = png_filename # Обновляем имя файла
        image.processed = True # Отмечаем как обработанное
        image.save()
        
        # Удаляем старый DICOM файл (опционально)
        # if dcm_path != converted_png_path:
        #     try:
        #         os.remove(dcm_path)
        #         print(f"Removed original DICOM file: {dcm_path}")
        #     except OSError as e:
        #         print(f"Error removing original DICOM file {dcm_path}: {e}")
                
        messages.success(request, f"Изображение успешно преобразовано в PNG: {png_filename}")
    else:
        messages.error(request, "Ошибка при преобразовании изображения.")
        
    return redirect('image_detail', image_id=image_id)
