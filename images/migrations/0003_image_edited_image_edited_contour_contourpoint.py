# Generated by Django 4.2.20 on 2025-05-20 19:49

from django.db import migrations, models
import django.db.models.deletion
import images.models


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0002_image_prediction_mask_image_processed_image_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='edited',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='image',
            name='edited_contour',
            field=models.FileField(blank=True, null=True, upload_to=images.models.user_directory_path),
        ),
        migrations.CreateModel(
            name='ContourPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('x', models.IntegerField(help_text='X-координата точки контура')),
                ('y', models.IntegerField(help_text='Y-координата точки контура')),
                ('order', models.IntegerField(help_text='Порядковый номер точки в контуре')),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='contour_points', to='images.image')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
    ]
