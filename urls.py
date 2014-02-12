################################################################################
#
#   Copyright (c) 2011-2013, Alexander Todorov <atodorov@nospam.dif.io>
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


from django.contrib import admin
admin.autodiscover()

from settings import STATIC_NOVER_URL
from django.contrib.auth import views as auth_views
from django.conf.urls import patterns, include, url

URL_INDEX = ''
from utils import URL_ADVISORIES
URL_SEARCH = 'search'
URL_ROBOTSTXT = 'robots.txt'
URL_ANALYTICS = 'analytics'

handler404 = 'difio.views.view_404'
handler500 = 'difio.views.view_500'

urlpatterns = patterns('',
    url(r'^%s$' % URL_INDEX, 'difio.views.index', name='index'),
    url(r'^%s/$' % URL_SEARCH, 'difio.views.search_results', name='search_results'),
    url(r'^%s/$' % URL_ANALYTICS,  'difio.views.analytics', name='analytics'),

    # /updates/django-1.3/django-1.3.1/245
    url(r'^%s/(?P<old>.*)/(?P<new>.*)/(?P<id>\d+)/$' % URL_ADVISORIES, 'difio.views.advisory', name='advisory'),

    # AJAX API
    url(r'^ajax/update/app/name/$', 'difio.views.ajax_update_app_name', name='ajax_update_app_name'),
    url(r'^ajax/update/app/url/$', 'difio.views.ajax_update_app_url', name='ajax_update_app_url'),
    url(r'^ajax/delete/InstalledPackage/$', 'difio.views.ajax_delete_inst_pkg', name='ajax_delete_inst_pkg'),
    url(r'^ajax/delete/application/$', 'difio.views.ajax_app_delete', name='ajax_delete_application'),
    url(r'^ajax/delete/bug/$', 'difio.views.ajax_delete_bug', name='ajax_delete_bug'),
    url(r'^ajax/approve/application/$', 'difio.views.ajax_app_approve', name='ajax_approve_app'),
    url(r'^ajax/invite_friends/$', 'difio.views.ajax_invite_friends', name='ajax_invite_friends'),
    url(r'^ajax/search/packages/(?P<uuid>.*)/$', 'difio.views.ajax_search_packages', name='ajax_search_packages'),
    url(r'^ajax/reminder/social_provider/$', 'difio.views.ajax_reminder_social_provider', name='ajax_reminder_social_provider'),

    # registration endpoints
    url(r'^application/register/$', 'difio.views.application_register'),
    url(r'^application/import/pip-freeze/$', 'difio.views.application_import_pip_freeze', name="import_pipfreeze"),     # Python
    url(r'^application/import/bundle-list/$', 'difio.views.application_import_bundle_list', name="import_bundle_list"), # Ruby
    url(r'^application/import/npm-ls/$', 'difio.views.application_import_npm_ls', name="import_npm_ls"),                # Node.js
    url(r'^application/import/perllocal.pod/$', 'difio.views.application_import_perllocal', name="import_perllocal"),   # Perl
    url(r'^application/import/mvn-dependency-list/$', 'difio.views.application_import_maven', name="import_maven"),     # Java / Maven
    url(r'^application/import/composer-show/$', 'difio.views.application_import_composer', name="import_composer"),     # PHP w/ Composer

    # web hooks
    url(r'^hook/rubygems/$', 'difio.views.hook_rubygems', name="hook_rubygem"), # Ruby

    # dashboard
    url(r'^dashboard/$',        'difio.views.myapps_new',      name='dashboard'),

    # apps management
    # NB: this is hard-coded in approve.js to redirect after app approval
    url(r'^applications/(?P<id>\d+)/$', 'difio.views.appdetails', name='appdetails'),
    url(r'^applications/history/(?P<id>\d+)/$', 'difio.views.app_history', name='app_history'),

    # static urls
    url(r'^%s$' % URL_ROBOTSTXT,  'difio.views.view_robotstxt', name='robotstxt'),

    # user handling
    # NB: must match settings.py
    url(r'^login/$', auth_views.login, {'template_name': 'registration/login-social.html', 'extra_context' : {'STATIC_NOVER_URL':STATIC_NOVER_URL}}, name='auth_login'),
    url(r'^logout/$', auth_views.logout, {'template_name': 'registration/logout.html', 'extra_context' : {'STATIC_NOVER_URL':STATIC_NOVER_URL}}, name='auth_logout'),
    url(r'^login-error/$', 'difio.views.error', name='login_error'),

    # django admin pages
    url(r'^admin/', include(admin.site.urls)),
)

try:
    import local_urls
    urlpatterns += local_urls.urlpatterns
except:
    pass

# if this URL path is not overriden in local_urls.py (Django uses first-match) then show
# a mock profile view. NB: KEEP `name' the same b/c is used through out the templates
urlpatterns += patterns('',
    url(r'^profiles/mine/$', 'difio.views.mock_profile_details', name='profiles_my_profile_detail'),
)