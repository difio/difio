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
# This module provides a simple template tag which returns the text/image used
# for logo in the upper left corner of the templates. By default it says
# Difio Open Source
#
################################################################################

from django.conf import settings
from django.template import Library

register = Library()


@register.simple_tag
def difio_logo():
    logo_text = getattr(settings, "DIFIO_LOGO_HTML", "<h1><a class='logo'>difio</a><sub>open source</sub></h1>")
    return logo_text
