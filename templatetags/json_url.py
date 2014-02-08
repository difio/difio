################################################################################
#
#   Copyright (c) 2014, Alexander Todorov <atodorov@nospam.dif.io>
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
#
# This module provides a simple template tag which points to the correct URL
# for json files like changelog.json, commitlog.json, etc.
#
################################################################################

from django.template import Library
from django.core.files.storage import default_storage

register = Library()


@register.simple_tag
def json_url(path):
    """
    A template tag that returns the URL to a file
    using the default storage backend.
NB: In case the DEFAULT_STORAGE is not Amazon S3 this may cause
a backtrace.
    """
    return default_storage.url(path)

@register.simple_tag
def json_base_url(path):
    """
    A template tag that returns the base URL to a file
    using the default storage backend.
    """
    url = json_url(path)
    return url.split(path)[0]
