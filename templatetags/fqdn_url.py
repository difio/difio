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
#
# This module extends the standard `url' template tag in Django and adds support
# for fully qualified domain name URLs.
# It also can be extended with URL load balancing techniques if desired.
#
################################################################################

try:
    from settings import FQDN
except:
    FQDN = ""

# Note: we could use the sites framework but it stores the domain in the DB
# not in local_settings.py which I don't like. It's also missing support for
# web clusters which can serve the same content over different URLs

from django.template import Library
from django.template import defaulttags
from django.templatetags import future


register = Library()


class FQDN_URLNode(defaulttags.URLNode):
    def render(self, context):
        retval = super(FQDN_URLNode, self).render(context)
        retval = FQDN + retval

        if self.asvar:
            context[self.asvar] = retval
            return ''
        else:
            return retval

@register.tag
def fqdn_url(parser, token):
    # NB change with defaulttags.url for Django 1.5 and later
    retval = future.url(parser, token)
    retval.__class__ = FQDN_URLNode

    return retval
