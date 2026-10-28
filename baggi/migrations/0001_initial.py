from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ConsultationRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('interest', models.CharField(choices=[('weight-management', 'Weight management'), ('lifestyle-coaching', 'Healthy lifestyle coaching'), ('nutrition-education', 'Nutrition education'), ('fitness-challenges', 'Fitness challenges'), ('nutrition-products', 'Nutrition products'), ('business-opportunity', 'Business opportunity')], max_length=40)),
                ('goals', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-submitted_at']},
        ),
    ]
