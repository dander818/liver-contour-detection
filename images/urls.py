from django.urls import path
from . import views

urlpatterns = [
    path('images/', views.image_list, name='image_list'),
    path('images/upload/', views.image_upload, name='image_upload'),
    path('images/<int:image_id>/', views.image_detail, name='image_detail'),
    path('images/<int:image_id>/delete/', views.image_delete, name='image_delete'),
    path('images/<int:image_id>/process/', views.process_image, name='process_image'),
] 