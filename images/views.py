from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ImageUploadForm
from .models import Image
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
