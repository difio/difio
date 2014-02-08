################################################################################
#
#   Originally based on http://djangosnippets.org/snippets/1016/
#   with small modifications
#
################################################################################


import re
from django.contrib import admin
from django.conf.urls import patterns, url
from django.http import HttpResponseRedirect

class ButtonableModelAdmin(admin.ModelAdmin):
    """
        A subclass of this admin will let you add buttons (like history) in the
        change view of an entry.
    """
    buttons = []

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if not extra_context:
            extra_context = {'buttons' : []}

        for b in self.buttons:
            extra_context['buttons'].append({'name' : b.short_description, 'url' : b.func_name})

        return super(ButtonableModelAdmin, self).change_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        urls = super(ButtonableModelAdmin, self).get_urls()

        my_urls = patterns('',)
        for b in self.buttons:
            my_urls += patterns('',
                            url(r'^(?P<id>\d+)/%s/$' % b.func_name, self.admin_site.admin_view(b))
                        )

        return my_urls + urls

    def __call__(self, request, url):
        if url is not None:
            res=re.match('(.*/)?(?P<id>\d+)/(?P<command>.*)/', url)
            if res:
                if res.group('command') in [b.func_name for b in self.buttons]:
                    obj = self.model._default_manager.get(pk=res.group('id'))
                    getattr(self, res.group('command'))(obj)
                    return HttpResponseRedirect(request.META['HTTP_REFERER'])

        return super(ButtonableModelAdmin, self).__call__(request, url)
