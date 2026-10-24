
import os

from celery import Celery

# Set the default Django settings module
os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'hr_payroll.settings'
)

# Create the Celery application
app = Celery('hr_payroll')

# Load Celery configuration from Django settings
app.config_from_object(
    'django.conf:settings',
    namespace='CELERY'
)

# Automatically discover tasks.py in Django apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
