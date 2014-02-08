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
# This module provides a simple template tag which points to the URL where
# static, non-versioned files are stored. 
#
################################################################################

from django.template import Node
from django.template import Library
try:
    from settings import STATIC_NOVER_URL
except:
    STATIC_NOVER_URL = ""


register = Library()


class NoVerURLNode(Node):
    def __init__(self, asvar):
        self.asvar = asvar

    def render(self, context):
        retval = STATIC_NOVER_URL

        if self.asvar:
            context[self.asvar] = retval
            return ''
        else:
            return retval

@register.tag
def static_nover_url(parser, token):
    asvar = None
    bits = token.split_contents()
    if 'as' in bits:
        asvar = bits[-1]

    return NoVerURLNode(asvar)
