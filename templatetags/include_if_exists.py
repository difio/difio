#
# Based on 
# http://stackoverflow.com/questions/6216760/check-if-a-template-exists-within-a-django-template
#

from django import template
from django.template.loader_tags import do_include
from django.template.defaulttags import CommentNode
register = template.Library()

@register.tag('include_if_exists')
def do_include_if_exists(parser, token):
    try:
        return do_include(parser, token)
    except template.TemplateDoesNotExist:
        return CommentNode()
