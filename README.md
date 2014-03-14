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

Difio depends on several external components which need to be installed and
pre-configured on the server before installing difio/.

* Django - new or existing project;
* ClamAV - for anti virus scanning;
* Web server for JSON content (Apache, Nginx, etc);
* Database;
* Messaging layer (RabbitMQ, Amazon SQS, etc);
* Periodic task scheduler (cron, celerybeat, etc);


* First install the web application:

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
# Difio needs CORS enabled, for Apache add to your config:
#    Header set Access-Control-Allow-Origin      "*"
#    Header set Access-Control-Allow-Headers     "content-type, x-requested-with"
#    Header set Access-Control-Allow-Methods     "GET"
# See http://enable-cors.org/server_apache.html
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

* Initialize the database schema:

        $ python manage.py syncdb

* Optionally obtain API keys from http://rubygems.org and register a web hook to import
new gems:

        $ curl -H 'Authorization:00000000000000000000' \
               -F 'gem_name=*' -F 'url=http://example.com/difio/hook/rubygems/' \
               https://rubygems.org/api/v1/web_hooks


* Configrue a periodic task scheduler to execute some of the maintenance tasks
at regular intervals. Following is a list of tasks and execution frequencies

        # daily tasks
        difio.tasks.cron_notify_app_owners_1            # send daily email notifications

        # flexible interval tasks:
        # - depend on how often do you want to query upstream;
        # - depend on available computing resources (less frequent execution, less resources needed)
        difio.tasks.cron_delete_pending_apps            # deletes apps which were not approved
        difio.tasks.cron_import_new_versions_from_rss   # imports new versions from upstream RSS feeds
        difio.tasks.cron_find_new_versions              # alternatively query upstream for the latest version
        difio.tasks.cron_generate_advisory_files        # generate analytics report (aka Advisory)
        difio.tasks.cron_move_advisories_to_live        # everything in state PUSHED_LIVE becomes LIVE


The following script may be used as a cron helper:

``` bash
#!/bin/bash
#
# Copyright (c) 2012-2013, Alexander Todorov <atodorov@nospam.dif.io>
#
# SYNOPSIS
#
# ./run_task module.tasks.task_name
#
# OR
#
# ln -s run_task module.tasks.task_name
#

TASK_NAME=$1
[ -z "$TASK_NAME" ] && TASK_NAME=$(basename $0)
MODULE_NAME=`echo "$TASK_NAME" | rev | cut -f2- -d. | rev`

source ~/.virtualenvs/$CHANGE_ME/bin/activate
APP_DIR="~/$CHANGE_ME/app"

echo "import $MODULE_NAME; $TASK_NAME.delay()" | $APP_DIR/manage.py shell
```

In case you decide to use Celerybeat see the
[Periodic Tasks](http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html)
document.


* After the web application is installed Difio will start recording information
from upstream sources as well as user input. It will compare currently listed package
versions in the DB with the latest available and schedule analytics actions. This is
done in long-running background tasks using Celery. These are called workers in
Celery terms.
A worker consists of the same application code, including same settings.py and
configuration to start the worker daemon. Please see
[Workers Guide](http://docs.celeryproject.org/en/latest/userguide/workers.html) and 
[Running the worker as a daemon](http://docs.celeryproject.org/en/latest/tutorials/daemonizing.html)
for more information.


* Most of Difio operations are automated but analytics content needs to be
verified by person before it is published. This is to eliminate possible errors
and account for cases which were not automated. See *Content Administration Guide*
for more details;


Warnings
--------

In case you see problems with pycurl and SSL support check these resources:
* http://stackoverflow.com/questions/7391638/pycurl-installed-but-not-found
* https://bugzilla.redhat.com/show_bug.cgi?id=1073648
* https://github.com/pycurl/pycurl/pull/147

Building the sources locally (with --libs instead of --static-libs) and installing
may be used in some cases!
