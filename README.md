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

# this defines AWS CALLING FORMAT
from boto.s3.connection import *

DEFAULT_FROM_EMAIL = 'difio@example.com' # used when sending notifications
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend' # configure if not using the default one

##### Default protocol and domain name settings
FQDN="http://example.com"

#### JSON storage
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
DEFAULT_S3_PATH = "media" # unused

# django storages settings
AWS_S3_ACCESS_KEY_ID='xxxxxxxxxxxxxxxxxxxx'
AWS_S3_SECRET_ACCESS_KEY='YYYYYYYYYYYYYYYY'
AWS_STORAGE_BUCKET_NAME='www.example.com'
AWS_S3_CALLING_FORMAT=ProtocolIndependentOrdinaryCallingFormat()
AWS_QUERYSTRING_AUTH=False


##### STATIC FILES SETTINGS
STATICFILES_STORAGE = 's3_folder_storage.s3.StaticStorage'

STATIC_DOMAIN = '//example.cloudfront.net'  # CDN origins need to be configured manually with the CDN provider

STATIC_S3_PATH = 'static/v01/'
STATIC_NOVER_PATH = 'static/nv/'
STATIC_URL       = '%s/%s' % (STATIC_DOMAIN, STATIC_S3_PATH)
STATIC_NOVER_URL = '%s/%s' % (STATIC_DOMAIN, STATIC_NOVER_PATH)

STATICFILES_DIRS = ()

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder', # for nv/ DEBUG only Todo: fix it
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)


TEMPLATE_LOADERS = (
    'django.template.loaders.app_directories.Loader',
)

INSTALLED_APPS = (
# NB: ordered first b/c they override admin templates
    'difio',
    'djcelery',
    'djkombu',
    'storages',
    's3_folder_storage',
)





# user profiles settings
AUTH_PROFILE_MODULE = "difio.MockProfile"

# GitHub auth tokens
GITHUB_APP_ID                = '00000000000000000000'
GITHUB_API_SECRET            = '77777777777777777777'

##### RubyGems.org API key
RUBYGEMS_API_KEY = '00000000000000000000000000000000'


##### CELERY MESSAGING SETTINGS
CELERY_DEFAULT_QUEUE = 'difio'
CELERY_QUEUES = {
    CELERY_DEFAULT_QUEUE: {
        'exchange': CELERY_DEFAULT_QUEUE,
        'binding_key': CELERY_DEFAULT_QUEUE,
    }
}

BROKER_USE_SSL = True
BROKER_TRANSPORT_OPTIONS = {
    'region': 'us-east-1',
}
BROKER_URL = "sqs://XXXXXXXXXXXXXXXXXXXX:YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY@"

CELERYBEAT_SCHEDULER = 'djcelery.schedulers.DatabaseScheduler'
CELERY_IGNORE_RESULT = True
CELERY_DISABLE_RATE_LIMITS = True

##### CACHE SETTINGS
CACHES = {
# Cache used for temporary objects like email hashes
# used for address verification
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache', # TODO: FIX ME 
        'TIMEOUT' : 60*60*24*30, # 1 month timeout
    },
# Cache used to pass larger objects to tasks to avoid
# hitting SQS message size limit. Uses different sub-path
    'taskq': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache', # TODO: FIX ME
        'TIMEOUT' : 60*60*24, # 1 day timeout
    },
}

```
