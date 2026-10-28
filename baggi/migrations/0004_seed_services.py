from django.db import migrations

STARTER_SERVICES = [
    ('wellness-evaluation', 'Wellness evaluation', '✳',
     'A friendly one-to-one chat about your routine, eating habits and goals to find a simple starting point.'),
    ('weight-management', 'Weight management', '↗',
     'Personal coaching and regular check-ins to help you build balanced habits for healthy weight loss or gain.'),
    ('nutrition-coaching', 'Nutrition coaching', '◌',
     'Practical guidance on balanced meals, protein, hydration and everyday choices that fit your lifestyle.'),
    ('fitness-challenges', 'Group fitness challenges', '✦',
     'Stay motivated with community challenges, group sessions and progress support alongside others.'),
]


def seed_services(apps, schema_editor):
    Service = apps.get_model('baggi', 'Service')
    for order, (slug, title, icon, summary) in enumerate(STARTER_SERVICES, start=1):
        Service.objects.get_or_create(
            slug=slug,
            defaults={'title': title, 'icon': icon, 'summary': summary, 'display_order': order},
        )


def remove_services(apps, schema_editor):
    apps.get_model('baggi', 'Service').objects.filter(
        slug__in=[slug for slug, *_ in STARTER_SERVICES],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('baggi', '0003_wellness_coaching'),
    ]

    operations = [
        migrations.RunPython(seed_services, remove_services),
    ]
