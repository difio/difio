################################################################################
#
#   Copyright (c) 2013, Alexander Todorov <atodorov@nospam.dif.io>
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


from functools import wraps
from django.core.cache import cache

def execute_once_in(seconds):
    """
    This decorator wraps a normal function
    so that it can be executed only once in the next few seconds.

    Useful to make Celery email sending tasks idempotent and safeguard
    against SQS messages delivered twice (in rare cases).

TODO: allow a parameter for the cache key to make for more flexible
decoration when sending to particular users/subjects as well.

    Usage:

    @task
    @execute_once_in(3600)
    def myfunction():                    # FALSE NEGATIVE
        pass

    If called multiple times, the above method will be executed only one
    time during the next hour following its first execution.
    """

    def decorator(func):  # FALSE NEGATIVE
        def inner_decorator(*args, **kwargs):  # FALSE NEGATIVE
            key = "%s.%s" % (func.__module__, func.__name__)
            key = key.replace(' ','_') # memcache doesn't like spaces

            # NB: there's no way to tell if
            # func() didn't execute or returned nothing
            if cache.get(key):
                return

            cache.set(key, True, seconds)
            return func(*args, **kwargs)


        return wraps(func)(inner_decorator)

    return decorator
