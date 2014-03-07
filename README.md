What is Difio
-------------

"If an application works, any change in its libraries or the versions of those
libraries can break the application." - virtualenv

Difio keeps track of packages and tells you when they change.
It provides multiple change analytics so you can make an informed decision when
or what to upgrade. Difio seeks to minimize the risk of upgrading upstream packages
inside your applications.

Difio is a Django based application. For development queries please head to the
[difio-devel](https://groups.google.com/forum/#!forum/difio-devel) group.


Supported programming languages and package sources
---------------------------------------------------

The following programming languages and package sources are supported:

* Java - http://search.maven.org
* Node.js - https://www.npmjs.org
* Perl - http://search.cpan.org
* PHP - https://packagist.org, http://pear.php.net, http://pear2.php.net
* Python - https://pypi.python.org/pypi
* Ruby - https://rubygems.org


Copyright
---------

Difio was initially developed by [Alexander Todorov](https://github.com/atodorov)
and [Svetlozar Argirov](https://github.com/zaro) for [www.dif.io](http://www.dif.io).

Difio, except where otherwise noted, is released under the
[Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0.html).
See the LICENSE file located in this directory.

How to install
---------------

    $ django-admin.py startproject mysite
    $ cd mysite/
    $ git clone https://github.com/difio/difio
    $ pip install -r difio/requirements.txt

Configure `urls.py`:

    url(r'^difio/', include('difio.urls')),

Configure `settings.py`. See the comments inline.

``` python

# loads Celery 
import djcelery
djcelery.setup_loader()


# configure the database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}



# First define apps part of difio/ then the rest of your site
INSTALLED_APPS = (
# NB: ordered first b/c they override admin templates
    'difio',
    'djcelery',
# other apps go below
)



# email configuration for sending notifications
DEFAULT_FROM_EMAIL = 'difio@example.com'
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'



##### Default protocol and domain name settings
FQDN="http://example.com" # optional



#### JSON storage
# this setting is used to write the JSON files containing
# analytics data, which are then loaded by the web page using AJAX
DEFAULT_FILE_STORAGE = 'difio.filestorage.OverwriteFileSystemStorage'
MEDIA_ROOT = "/tmp/example.com/files"    # where to store these files
MEDIA_URL = "http://example.com/files/"  # where to serve them from


##### STATIC FILES SETTINGS
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
STATIC_ROOT = '/tmp/example.com/static'
STATIC_URL  = '/static/'

# List of finder classes that know how to find static files in various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)



TEMPLATE_LOADERS = (
    'django.template.loaders.app_directories.Loader',
)



##### User profiles settings - replace with your own implementation
# with get_email_delay(), is_subscribed() and get_subscription_plan_name()
# methods. See the actual implementation for more details.
AUTH_PROFILE_MODULE = "difio.MockProfile"



##### GitHub auth tokens
# used by github.py for authenticated requests
# unauthenticated requests are severely limited.
# See http://developer.github.com/v3/#rate-limiting
# github.py uses OAuth2 Key/Secret authentication , see
# http://developer.github.com/v3/#authentication
# You will have to register an application with GitHub
# in order to be issued these tokens

# GITHUB_APP_ID                = '00000000000000000000'
# GITHUB_API_SECRET            = '77777777777777777777'



##### RubyGems.org API key
# used for importing packages via RubyGems.org web hooks
# http://guides.rubygems.org/rubygems-org-api/#webhook_methods
# If this is defined importing from RSS will be disabled automatically

# RUBYGEMS_API_KEY = '00000000000000000000000000000000'



##### CELERY MESSAGING SETTINGS
CELERY_DEFAULT_QUEUE = 'difio'
CELERY_QUEUES = {
    CELERY_DEFAULT_QUEUE: {
        'exchange': CELERY_DEFAULT_QUEUE,
        'binding_key': CELERY_DEFAULT_QUEUE,
    }
}

BROKER_USE_SSL = True
BROKER_URL = "amqp://"

CELERY_IGNORE_RESULT = True
CELERY_DISABLE_RATE_LIMITS = True
# using pickle b/c we pass date-time and callback parameters
# make sure to secure access to your message broker
CELERY_ACCEPT_CONTENT = ['pickle']
CELERY_TASK_SERIALIZER = 'pickle'

# ONLY FOR LOCAL DEVELOPMENT UNTILL THERE'S A UNIX SOCKET BROKER
# http://docs.celeryproject.org/en/latest/configuration.html#celery-always-eager
# CELERY_ALWAYS_EAGER = True
# CELERY_EAGER_PROPAGATES_EXCEPTIONS = True



##### CACHE SETTINGS
# NB: change FileBasedCache to what you use or leave unmodified otherwise
# DO NOT use LocMemCache because **cross-process caching is NOT possible**.

CACHES = {
# Used for temporary objects like email hashes
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION' : '/tmp/example.com/cache/default',
        'TIMEOUT' : 60*60*24*30, # 1 month timeout
    },
# Used to pass larger objects to tasks to avoid hitting message bus size limit
    'taskq': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION' : '/tmp/example.com/cache/taskq',
        'TIMEOUT' : 60*60*24, # 1 day timeout
    },
}

```


$ python manage.py syncdb

* Create user (assign permissions) which will be the content editor

* Register RubyGems.org web hook (optional)

* Configrue CRON scheduler or 
CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'


Warnings
--------

In case you see problems with pycurl and SSL support check these resources:
* http://stackoverflow.com/questions/7391638/pycurl-installed-but-not-found
* https://bugzilla.redhat.com/show_bug.cgi?id=1073648
* https://github.com/pycurl/pycurl/pull/147

Building the sources locally (with --libs instead of --static-libs) and installing
may be used in some cases!
