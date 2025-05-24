from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseBadRequest, JsonResponse
from .forms import ImageUploadForm
from .models import Image, ContourPoint
from .utils import dcm_to_png, nii_to_png  # Утилиты конвертации
from .prediction import load_prediction_model, get_prediction_mask, save_prediction_mask_image, save_contour_mask_for_extraction # Утилиты предсказания
import os
import json
import numpy as np
import cv2
from PIL import Image as PILImage
import matplotlib.pyplot as plt
import logging  # Добавляем импорт логгера

# Получаем логгер
logger = logging.getLogger(__name__)

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
                 
        # Удаляем файл с отредактированным контуром
        if image.edited_contour and hasattr(image.edited_contour, 'path') and os.path.isfile(image.edited_contour.path):
             try:
                 os.remove(image.edited_contour.path)
             except OSError as e:
                 print(f"Error removing edited contour file {image.edited_contour.path}: {e}")

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
            
            # --- 4. Сохранение КОНТУРНОЙ МАСКИ для извлечения точек ---
            contour_filename = f"{base_filename}_contour.png"
            contour_save_path = os.path.join(settings.MEDIA_ROOT, user_dir, contour_filename)
            contour_model_path = os.path.join(user_dir, contour_filename)
            
            if save_prediction_mask_image(converted_png_path, prediction_mask_array, overlay_save_path):
                image_instance.prediction_mask.name = overlay_model_path
                messages.success(request, f"Результат обработки с наложением маски успешно создан: {overlay_filename}")
            else:
                messages.error(request, "Ошибка при сохранении изображения с наложением маски.")
                
            if save_contour_mask_for_extraction(converted_png_path, prediction_mask_array, contour_save_path):
                image_instance.contour_mask.name = contour_model_path
                messages.success(request, f"Контурная маска для извлечения точек создана: {contour_filename}")
            else:
                messages.error(request, "Ошибка при сохранении контурной маски.")
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

@login_required
def edit_contour(request, image_id):
    """Отображает страницу для ручного редактирования контура."""
    image_instance = get_object_or_404(Image, id=image_id, user=request.user)
    
    if not image_instance.processed or not image_instance.prediction_mask:
        messages.error(request, "Для редактирования контура необходимо сначала обработать изображение.")
        return redirect('image_detail', image_id=image_id)
    
    # Получаем существующие точки контура, сгруппированные по contour_id
    all_contour_points = image_instance.contour_points.all().order_by('contour_id', 'order')
    
    # Группируем точки по contour_id
    contours_dict = {}
    for point in all_contour_points:
        if point.contour_id not in contours_dict:
            contours_dict[point.contour_id] = []
        contours_dict[point.contour_id].append({'x': point.x, 'y': point.y})
    
    # Преобразуем в список контуров для JavaScript
    contours_list = []
    for contour_id in sorted(contours_dict.keys()):
        contours_list.append(contours_dict[contour_id])
    
    # Если ручных точек нет, пытаемся извлечь из автоматического контура
    auto_contour_points = []
    if not contours_list and image_instance.contour_mask:
        try:
            # Получаем размеры processed_image для масштабирования
            processed_img = PILImage.open(image_instance.processed_image.path)
            target_width, target_height = processed_img.size
            
            auto_contour_points = extract_contour_points_from_mask(
                image_instance.contour_mask.path, 
                target_size=(target_width, target_height)
            )
            logger.info(f"Извлечено {len(auto_contour_points)} точек из автоматического контура, масштабировано к {target_width}x{target_height}")
        except Exception as e:
            logger.error(f"Не удалось извлечь автоматический контур: {e}")
    elif not contours_list and image_instance.prediction_mask:
        # Fallback на старую заливочную маску если контурной нет
        try:
            processed_img = PILImage.open(image_instance.processed_image.path)
            target_width, target_height = processed_img.size
            
            auto_contour_points = extract_contour_points_from_mask(
                image_instance.prediction_mask.path, 
                target_size=(target_width, target_height)
            )
            logger.info(f"Извлечено {len(auto_contour_points)} точек из маски заливки (fallback)")
        except Exception as e:
            logger.error(f"Не удалось извлечь контур из маски заливки: {e}")
    
    context = {
        'image': image_instance,
        'contours': json.dumps(contours_list),  # Множественные контуры
        'auto_contour_points': json.dumps(auto_contour_points),  # Автоматические точки
        'has_manual_contours': len(contours_list) > 0,
        'has_auto_contour': len(auto_contour_points) > 0,
    }
    
    return render(request, 'images/edit_contour.html', context)

@login_required
def save_edited_contour(request, image_id):
    """Сохраняет отредактированный контур."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST requests are allowed'}, status=400)
    
    try:
        logger.info(f"Получен запрос на сохранение контура для изображения ID={image_id}")
        image_instance = get_object_or_404(Image, id=image_id, user=request.user)
        
        try:
            data = json.loads(request.body)
            logger.info(f"Получены данные JSON: {data.keys()}")
            contour_points = data.get('points', [])
            contours_structure = data.get('contours', [])
            logger.info(f"Количество точек контура: {len(contour_points)}")
            logger.info(f"Количество контуров: {len(contours_structure)}")
            
            if not contour_points:
                return JsonResponse({'success': False, 'error': 'No contour points provided'}, status=400)
            
            # Удаляем существующие точки контура
            count_deleted = image_instance.contour_points.all().delete()
            logger.info(f"Удалено существующих точек: {count_deleted}")
            
            # Сохраняем новые точки контура с учетом contour_id
            for i, point in enumerate(contour_points):
                contour_id = point.get('contour_id', 0)
                ContourPoint.objects.create(
                    image=image_instance,
                    x=point['x'],
                    y=point['y'],
                    order=i,
                    contour_id=contour_id
                )
            logger.info(f"Сохранено {len(contour_points)} новых точек контура")
            
            # Создаем изображение контура
            if image_instance.processed_image:
                logger.info(f"Загружаем обработанное изображение: {image_instance.processed_image.path}")
                # Загружаем обработанное изображение для получения размеров
                img = PILImage.open(image_instance.processed_image.path)
                width, height = img.size
                logger.info(f"Размеры изображения: {width}x{height}")
                
                # Создаем маску контуров
                mask = np.zeros((height, width, 3), dtype=np.uint8)
                logger.info("Создана пустая маска")
                
                # Группируем точки по контурам
                contours_by_id = {}
                for point in contour_points:
                    contour_id = point.get('contour_id', 0)
                    if contour_id not in contours_by_id:
                        contours_by_id[contour_id] = []
                    contours_by_id[contour_id].append([point['x'], point['y']])
                
                logger.info(f"Сгруппировано в {len(contours_by_id)} контуров")
                
                try:
                    # Рисуем каждый контур разным цветом
                    colors = [
                        (255, 0, 0),    # Красный
                        (0, 255, 0),    # Зеленый
                        (0, 0, 255),    # Синий
                        (255, 255, 0),  # Желтый
                        (255, 0, 255),  # Пурпурный
                        (0, 255, 255),  # Циан
                    ]
                    
                    for contour_id, points_list in contours_by_id.items():
                        if len(points_list) < 3:
                            continue
                            
                        points_array = np.array(points_list, dtype=np.int32)
                        color = colors[contour_id % len(colors)]
                        
                        # Рисуем заливку контура
                        cv2.fillPoly(mask, [points_array], color)
                        
                        # Рисуем границу контура
                        cv2.polylines(mask, [points_array], isClosed=True, color=color, thickness=3)
                    
                    logger.info("Контуры успешно нарисованы на маске")
                    
                    # Создаем наложение контуров на исходное изображение
                    user_dir = os.path.dirname(image_instance.image.name)
                    base_filename = os.path.splitext(os.path.basename(image_instance.image.name))[0]
                    edited_contour_filename = f"{base_filename}_edited_contour.png"
                    edited_contour_path = os.path.join(settings.MEDIA_ROOT, user_dir, edited_contour_filename)
                    logger.info(f"Путь для сохранения изображения с контуром: {edited_contour_path}")
                    
                    # Проверяем существование директории и создаем ее при необходимости
                    os.makedirs(os.path.dirname(edited_contour_path), exist_ok=True)
                    logger.info(f"Проверено существование директории: {os.path.dirname(edited_contour_path)}")
                    
                    # Создаем изображение с наложением используя PIL
                    try:
                        # Конвертируем маску в PIL Image
                        mask_pil = PILImage.fromarray(mask, 'RGB')
                        
                        # Создаем композитное изображение
                        result = PILImage.blend(img.convert('RGB'), mask_pil, alpha=0.3)
                        
                        # Сохраняем результат
                        result.save(edited_contour_path, 'PNG')
                        logger.info(f"Изображение с контурами сохранено в: {edited_contour_path}")
                        
                        # Обновляем модель с путем к новому изображению
                        edited_contour_model_path = os.path.join(user_dir, edited_contour_filename)
                        image_instance.edited_contour.name = edited_contour_model_path
                        image_instance.edited = True
                        image_instance.save()
                        logger.info(f"Модель обновлена с новым путем к изображению: {edited_contour_model_path}")
                        
                        return JsonResponse({
                            'success': True, 
                            'message': f'Успешно сохранено {len(contours_by_id)} контуров',
                            'edited_contour_url': image_instance.edited_contour.url
                        })
                    except Exception as pil_error:
                        logger.error(f"Ошибка при создании или сохранении изображения с PIL: {pil_error}")
                        import traceback
                        logger.error(traceback.format_exc())
                        return JsonResponse({'success': False, 'error': f'Error creating image: {str(pil_error)}'}, status=500)
                except Exception as cv_error:
                    logger.error(f"Ошибка при работе с OpenCV: {cv_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return JsonResponse({'success': False, 'error': f'Error with OpenCV: {str(cv_error)}'}, status=500)
            else:
                logger.error("Не найдено обработанное изображение")
                return JsonResponse({'success': False, 'error': 'Processed image not found'}, status=400)
                
        except json.JSONDecodeError as json_error:
            logger.error(f"Ошибка декодирования JSON: {json_error}")
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Необработанная ошибка: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

def extract_contour_points_from_mask(mask_image_path, max_points=50, target_size=None):
    """Извлекает точки контура из контурной маски для инициализации ручного редактирования."""
    try:
        # Загружаем изображение маски
        img = PILImage.open(mask_image_path)
        img_array = np.array(img)
        logger.info(f"Загружено изображение контурной маски размером {img.width}x{img.height}")
        
        # Конвертируем в RGB если нужно
        if len(img_array.shape) == 3:
            # Ищем красные пиксели (контурные линии)
            # Красный канал должен быть высоким, а зеленый и синий - низкими
            red_channel = img_array[:, :, 0]
            green_channel = img_array[:, :, 1]
            blue_channel = img_array[:, :, 2]
            
            # Строгие условия для красных контурных линий
            red_mask = (red_channel > 200) & (green_channel < 100) & (blue_channel < 100)
            logger.info(f"Маска красных контурных линий: {np.sum(red_mask)} пикселей")
        else:
            # Для grayscale изображений
            red_mask = img_array > 127
            logger.info(f"Grayscale маска: {np.sum(red_mask)} пикселей")
        
        # Находим контуры
        contours, _ = cv2.findContours(red_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            logger.warning("Контуры не найдены в маске")
            return []
        
        logger.info(f"Найдено {len(contours)} контуров")
        
        # Берем самый большой контур
        largest_contour = max(contours, key=cv2.contourArea)
        contour_area = cv2.contourArea(largest_contour)
        logger.info(f"Выбран самый большой контур с площадью {contour_area}")
        
        # Если контур слишком маленький, это может быть артефакт
        if contour_area < 50:  # Понижаем порог для контурных линий
            logger.warning(f"Контур слишком маленький (площадь {contour_area}), пропускаем")
            return []
        
        # Упрощаем контур до нужного количества точек
        epsilon = cv2.arcLength(largest_contour, True) * 0.01  # Возвращаем к 1% для точности
        simplified_contour = cv2.approxPolyDP(largest_contour, epsilon, True)
        
        logger.info(f"Упрощенный контур содержит {len(simplified_contour)} точек")
        
        # Если точек все еще слишком много, берем равномерно распределенные
        if len(simplified_contour) > max_points:
            step = len(simplified_contour) // max_points
            simplified_contour = simplified_contour[::step]
            logger.info(f"Взято каждую {step}-ю точку, результат: {len(simplified_contour)} точек")
        
        # Конвертируем в список точек
        points = []
        for point in simplified_contour:
            x, y = point[0]
            points.append({'x': int(x), 'y': int(y)})
        
        logger.info(f"Извлечено {len(points)} точек контура из маски {img.width}x{img.height}")
        
        if target_size:
            # Масштабируем точки
            logger.info(f"Масштабирование с {img.width}x{img.height} к {target_size[0]}x{target_size[1]}")
            scaled_points = []
            for point in points:
                scaled_x = int(point['x'] * target_size[0] / img.width)
                scaled_y = int(point['y'] * target_size[1] / img.height)
                scaled_points.append({'x': scaled_x, 'y': scaled_y})
                logger.debug(f"Точка ({point['x']}, {point['y']}) -> ({scaled_x}, {scaled_y})")
            points = scaled_points
            logger.info(f"Масштабирование завершено, получено {len(points)} точек")
        
        return points
        
    except Exception as e:
        logger.error(f"Ошибка извлечения контура из маски {mask_image_path}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []
