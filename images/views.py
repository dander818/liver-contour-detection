from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseBadRequest
from .forms import ImageUploadForm
from .models import Image
from .utils import dcm_to_png, nii_to_png  # Утилиты конвертации
from .prediction import load_prediction_model, get_prediction_mask, save_prediction_mask_image # Утилиты предсказания
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
            image.save()
            messages.success(request, 'Изображение успешно загружено!')
            return redirect('original_image_list')
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
        # Удаляем оригинальный файл
        if image.image and hasattr(image.image, 'path') and os.path.isfile(image.image.path):
            try:
                os.remove(image.image.path)
            except OSError as e:
                print(f"Error removing original file {image.image.path}: {e}")
        # Удаляем обработанный файл (PNG)
        if image.processed_image and hasattr(image.processed_image, 'path') and os.path.isfile(image.processed_image.path):
            try:
                os.remove(image.processed_image.path)
            except OSError as e:
                print(f"Error removing processed file {image.processed_image.path}: {e}")
        
        # Удаляем файл с наложением маски (ранее был prediction_mask)
        if image.prediction_mask and hasattr(image.prediction_mask, 'path') and os.path.isfile(image.prediction_mask.path):
             try:
                 os.remove(image.prediction_mask.path)
             except OSError as e:
                 print(f"Error removing overlay image file {image.prediction_mask.path}: {e}")

        image.delete()
        messages.success(request, 'Запись и связанные файлы успешно удалены!')
        return redirect('original_image_list')
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
    user_dir = os.path.dirname(image_instance.image.name) # user_<id>/...
    base_filename = os.path.splitext(os.path.basename(image_instance.image.name))[0]

    # --- 1. Конвертация входного файла в PNG ---
    png_filename = f"{base_filename}_processed.png"
    png_save_path = os.path.join(settings.MEDIA_ROOT, user_dir, png_filename) # Полный путь для сохранения
    png_model_path = os.path.join(user_dir, png_filename) # Путь для модели Django

    os.makedirs(os.path.dirname(png_save_path), exist_ok=True)

    # Определяем тип файла по расширению
    file_ext = os.path.splitext(original_path)[1].lower()
    
    # Обработка в зависимости от типа файла
    converted_png_path = None
    if file_ext == '.dcm':
        converted_png_path = dcm_to_png(original_path, png_save_path)
        if converted_png_path:
            messages.success(request, f"DICOM изображение успешно преобразовано в PNG: {png_filename}")
    elif file_ext in ['.nii', '.gz']:
        converted_png_path = nii_to_png(original_path, png_save_path)
        if converted_png_path:
            messages.success(request, f"NIfTI изображение успешно преобразовано в PNG: {png_filename}")
    else:
        messages.error(request, f"Неподдерживаемый тип файла: {file_ext}. Поддерживаются только .dcm, .nii и .nii.gz файлы.")
        return redirect('image_detail', image_id=image_id)

    if not converted_png_path:
        messages.error(request, "Ошибка при преобразовании исходного изображения в PNG.")
        return redirect('image_detail', image_id=image_id)

    image_instance.processed_image.name = png_model_path # Сохраняем путь к PNG
    # Не ставим processed=True и не сохраняем image_instance пока

    # --- 2. Загрузка модели и предсказание --- 
    try:
        # Загружаем модель (путь к файлу модели задан по умолчанию в функции)
        model = load_prediction_model() 

        # Получаем маску предсказания
        prediction_mask_array = get_prediction_mask(converted_png_path, model)

        if prediction_mask_array is not None:
            # --- 3. Сохранение РЕЗУЛЬТАТА С НАЛОЖЕНИЕМ МАСКИ --- 
            overlay_filename = f"{base_filename}_overlay.png"
            overlay_save_path = os.path.join(settings.MEDIA_ROOT, user_dir, overlay_filename)
            overlay_model_path = os.path.join(user_dir, overlay_filename)
            
            if save_prediction_mask_image(converted_png_path, prediction_mask_array, overlay_save_path):
                image_instance.prediction_mask.name = overlay_model_path
                messages.success(request, f"Результат обработки с наложением маски успешно создан: {overlay_filename}")
            else:
                messages.error(request, "Ошибка при сохранении изображения с наложением маски.")
        else:
             messages.error(request, "Ошибка при генерации маски предсказания моделью.")

    except FileNotFoundError as e:
        messages.error(request, f"Ошибка загрузки модели: {e}. Убедитесь, что файл модели находится в папке ml_models/")
        # Обработка не удалась полностью, но PNG сохранен
    except Exception as e:
        messages.error(request, f"Произошла ошибка во время обработки моделью: {e}")
        # Обработка не удалась полностью, но PNG сохранен

    # --- 4. Финальное сохранение статуса --- 
    image_instance.processed = True
    image_instance.save()

    return redirect('image_detail', image_id=image_id)
