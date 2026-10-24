
"""
Django settings for hr_payroll project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


# =========================================================
# BASE DIRECTORY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the project-root .env
load_dotenv(BASE_DIR / '.env')


# =========================================================
# SECURITY SETTINGS
# =========================================================

# Development fallback only.
# Set DJANGO_SECRET_KEY before production.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-local-development-only-change-me'
)

DEBUG = os.environ.get(
    'DJANGO_DEBUG',
    'True'
).lower() == 'true'

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        'DJANGO_ALLOWED_HOSTS',
        ''
    ).split(',')
    if host.strip()
]


# =========================================================
# INSTALLED APPLICATIONS
# =========================================================

INSTALLED_APPS = [
    # Django applications
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party applications
    'rest_framework',

    # Project applications
    'accounts',
    'employees',
    'leave_management',
    'performance',
    'payroll',
    'audit',
    'notifications',

    'django_celery_beat',
]


# =========================================================
# GMAIL SMTP CONFIGURATION
# =========================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587

EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.environ.get(
    'EMAIL_HOST_USER', ''
).strip()

EMAIL_HOST_PASSWORD = os.environ.get(
    'EMAIL_HOST_PASSWORD', ''
).replace(' ', '').strip()

DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# =========================================================
# ACCOUNT INVITATION CONFIGURATION
# =========================================================

# Invitation links expire after 24 hours
ACCOUNT_INVITATION_TIMEOUT = 60 * 60 * 24


# =========================================================
# CELERY CONFIGURATION
# =========================================================

# Redis message broker
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'

# Store task results in Redis
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/1'

# Task serialization
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Timezone
CELERY_TIMEZONE = 'Australia/Melbourne'

# Use Django database for periodic task schedules
CELERY_BEAT_SCHEDULER = (
    'django_celery_beat.schedulers:DatabaseScheduler'
)

# Track when tasks start
CELERY_TASK_TRACK_STARTED = True


# =========================================================
# CUSTOM USER MODEL
# =========================================================

AUTH_USER_MODEL = 'accounts.UserAccount'


# =========================================================
# DJANGO REST FRAMEWORK
# =========================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],

    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# =========================================================
# URL CONFIGURATION
# =========================================================

ROOT_URLCONF = 'hr_payroll.urls'


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.notification_context',
            ],
        },
    },
]


# =========================================================
# WSGI APPLICATION
# =========================================================

WSGI_APPLICATION = 'hr_payroll.wsgi.application'


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
            'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME':
            'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME':
            'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME':
            'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# =========================================================
# INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Australia/Melbourne'

USE_I18N = True

USE_TZ = True


# =========================================================
# STATIC FILES
# =========================================================

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]


# =========================================================
# AUTHENTICATION SETTINGS
# =========================================================

LOGIN_URL = '/login/'

LOGIN_REDIRECT_URL = '/'

LOGOUT_REDIRECT_URL = '/login/'


# =========================================================
# DEFAULT PRIMARY KEY FIELD
# =========================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
