################################################################################
#
#   Copyright (c) 2011-2013, Alexander Todorov <atodorov@nospam.dif.io>
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
################################################################################


import os
import sys
import djcelery
djcelery.setup_loader()

DJANGO_PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))

# allow for a directory named local_settings/ adjacent to difio/
# which may hold a local_settings.py or local_urls.py private settings
sys.path.insert(0,
    os.path.realpath(
        os.path.join(DJANGO_PROJECT_DIR, '..', 'local_settings')
    )
)

# make sure difio/ is always in the Python path
# so we can do things like `import utils' instead of
# `from difio import utils'
if DJANGO_PROJECT_DIR not in sys.path:
    sys.path.insert(0, DJANGO_PROJECT_DIR)


##### USER PROFILE SETTING
# NB: override later in local_settings.py
AUTH_PROFILE_MODULE = "difio.MockProfile"


# import local settings first b/c there are
# private apps which need to go into INSTALLED_APPS
# and other private settings which are ammended with public ones
try:
    if 'TRAVIS' in os.environ:
        from travis_settings import *
    else:
        from local_settings import *
except ImportError:
    pass



##### MANAGERS SETTINGS
MANAGERS = ADMINS



##### DJANGO DEFAULTS SETTINGS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/Sofia'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1


# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/media/' # not used


# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = ''

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder', # for nv/ DEBUG only Todo: fix it
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)



MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
#    'htmlmin.middleware.HtmlMinifyMiddleware',
)



# by default HTML minify
HTML_MINIFY = False # latest htmlmin is worse than older versions



ROOT_URLCONF = 'difio.urls'


# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.static',
    'django.core.context_processors.csrf',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
    'social_auth.context_processors.social_auth_backends',
)



# Private apps are defined in local_settings.py
INSTALLED_APPS = INSTALLED_APPS + (
# NB: ordered first b/c they override admin templates
    'difio',
# stock apps
    'django.contrib.auth',
    'django.contrib.contenttypes', # TODO: IS THIS USED ??
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.markup',   ## TODO: IS THIS USED
# Celery
    'djcelery',
    'djkombu',
# django-storages
    'storages',
# django-s3-folder-storage
    's3_folder_storage',
)



# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}



# NB: must match urls.py
LOGIN_URL = '/login/'
LOGOUT_URL = '/logout/'
LOGIN_ERROR_URL    = '/login-error/'
LOGIN_REDIRECT_URL = '/dashboard/'



##### CELERY MESSAGING SETTINGS
CELERY_DEFAULT_QUEUE = 'difio'
CELERY_QUEUES = {
    CELERY_DEFAULT_QUEUE: {
        'exchange': CELERY_DEFAULT_QUEUE,
        'binding_key': CELERY_DEFAULT_QUEUE,
    }
}

CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'
# performance settings
CELERY_IGNORE_RESULT = True
CELERY_DISABLE_RATE_LIMITS = True

