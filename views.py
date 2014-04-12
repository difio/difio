################################################################################
#
#   Copyright (c) 2011-2014, Alexander Todorov <atodorov@nospam.dif.io>
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


import os
import re
import json
import uuid
import utils
import base64
import hashlib
import rubygems
import difio.tasks
import pkg_parsers
from forms import *
from models import *
from django.conf import settings
from django.core.cache import cache
from django.core import cache as cache_module
from django.shortcuts import render
from django.contrib import messages
from django.utils.html import escape
from datetime import datetime, timedelta
from django.db.models import Count, Q, Sum
from ratelimit.decorators import ratelimit
from django.template import RequestContext
from django.contrib.auth.models import User
from django.contrib.auth.decorators import *
from django.core.urlresolvers import reverse
from templated_email import send_templated_mail
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseRedirect
from django.core.paginator import Paginator, InvalidPage, EmptyPage

def analytics(request):
    return render(request, 'analytics.html')

def index(request):
    """
        Render the homepage.
    """
    context = {}
    FRONT_PAGE_PAGINATOR = 7

    remaining_updates_count = Advisory.objects.filter(status=STATUS_LIVE).count() - FRONT_PAGE_PAGINATOR
    if remaining_updates_count > 0:
        context['updates_count'] = remaining_updates_count
    else:
        context['updates_count'] = 0

    query = Advisory.objects.filter(status=STATUS_LIVE).only('id', 'type', 'severity').order_by('-new__released_on')[:FRONT_PAGE_PAGINATOR]
    context['updates'] = query

    return render(request, 'index.html', {'context' : context })


def search_results(request):
    """
        Page to show search results from Google CSE.
    """
    return render(request, 'search.html')


def advisory(request, old, new, id):
    """
        Show an individual advisory.
    """

    try:
        adv = Advisory.objects.filter(id=id, status=STATUS_LIVE)[0] # showing all fields. Change when JSON UI is done
    except IndexError:
        messages.error(request, "Advisory not found!")
        return HttpResponseRedirect(reverse('dashboard'))

    return render(request, 'apps/advisory.html', {'advisory' : adv })


@login_required
def ajax_update_app_name(request):
    """
        Update application name when manually imported. Used by Dojo.
        Only update name when not empty and app is owned by the current user.
    """
    if not request.POST:
        return HttpResponse("Not a POST", mimetype='text/plain', status=403)

    user_id = int(request.POST.get('user', 0))
    app_id = int(request.POST.get('app', 0))
    name = request.POST.get('name', "")

    if user_id == request.user.id:
        if not name:
            return HttpResponse("I'm a teapot", mimetype='text/plain', status=418) # (RFC 2324)

        affected = Application.objects.filter(pk=app_id, owner=request.user).update(name=name)
        if affected == 1:
            return HttpResponse("Name updated", mimetype='text/plain', status=200)
        else:
            return HttpResponse("Failed to update name", mimetype='text/plain', status=403)
    else:
        return HttpResponse("User missmatch", mimetype='text/plain', status=403)

@login_required
def ajax_update_app_url(request):
    """
        Update application URL when manually imported. Used by Dojo.
        Only update URL when not empty and app is owned by the current user.
    """
    if not request.POST:
        return HttpResponse("Not a POST", mimetype='text/plain', status=403)

    user_id = int(request.POST.get('user', 0))
    app_id = int(request.POST.get('app', 0))
    url = request.POST.get('url', "")

    if user_id == request.user.id:
        if not url:
            return HttpResponse("I'm a teapot", mimetype='text/plain', status=418) # (RFC 2324)

        affected = Application.objects.filter(pk=app_id, owner=request.user).update(url=url)
        if affected == 1:
            return HttpResponse("URL updated", mimetype='text/plain', status=200)
        else:
            return HttpResponse("Failed to update URL", mimetype='text/plain', status=403)
    else:
        return HttpResponse("User missmatch", mimetype='text/plain', status=403)

@login_required
def ajax_app_delete(request):
    """
        Delete Application.
    """

    if not request.POST:
        return HttpResponse("Not a POST", mimetype='text/plain', status=403)

    user_id = int(request.POST.get('user', 0))
    app_id = int(request.POST.get('app', 0))

    if user_id == request.user.id:
        difio.tasks.cron_delete_pending_apps.delay(app_id, user_id)
        return HttpResponse("Application is deleted!", mimetype='text/plain', status=200)
    else:
        return HttpResponse("User missmatch", mimetype='text/plain', status=403)


@login_required
def ajax_app_approve(request):
    """
        Approve the application.
    """
    if not request.POST:
        return HttpResponse("Not a POST", mimetype='text/plain', status=403)

    user_id = int(request.POST.get('user', 0))
    app_id = int(request.POST.get('app', 0))

    if user_id == request.user.id:
        affected = Application.objects.filter(
                                    pk=app_id,
                                    status=APP_STATUS_PENDING,
                                    owner=request.user
                                ).update(
                                    status=APP_STATUS_APPROVED,
                                    date_approved = datetime.now()
                                )
        if affected == 1:
            difio.tasks.helper_search_new_data.delay(app_id)

            return HttpResponse("Application is approved!", mimetype='text/plain', status=200)
        else:
            return HttpResponse("Can approve only your pending applications!", mimetype='text/plain', status=403)
    else:
        return HttpResponse("User missmatch", mimetype='text/plain', status=403)


@user_passes_test(lambda u: u.is_staff)
def ajax_delete_bug(request):
    """
        Delete Bug from Advisory.
    """

    if not request.POST:
        return HttpResponse("Not a POST", mimetype='text/plain', status=403)

    advisory_id = int(request.POST.get('advisory', 0))
    bug_id = int(request.POST.get('bug', 0))

    if request.user.is_staff:
        Bug.objects.filter(
                            pk=bug_id,
                            advisory=advisory_id,
                            advisory__status__lt=STATUS_LIVE,
                        ).delete()

        return HttpResponse("Bug deleted!", mimetype='text/plain', status=200)
    else:
        return HttpResponse("User missmatch", mimetype='text/plain', status=403)


@login_required
def ajax_delete_inst_pkg(request):
    """
        Delete installed packages from manually imported apps. Used by Dojo.
        Only delete when app/package is owned by the current user.
    """
    if not request.POST:
        return HttpResponse("Not a POST", mimetype='text/plain', status=403)

    user_id = int(request.POST.get('user', 0))
    installed_id = request.POST.get('installed', 0)

    if user_id == request.user.id:
        query = InstalledPackage.objects.filter(pk=installed_id, owner=request.user.pk)
        app_pks = set(inst.application for inst in query.only('application'))

        # finally delete the object(s) before generating any app/history data
        # to avoid race conditions
        query.delete()

        for app in app_pks:
            Application.objects.filter(pk=app, owner=request.user).update(last_checkin=datetime.now())
            difio.tasks.do_stuff_when_packages_change.delay(app)

        return HttpResponse("Deleted successfully", mimetype='text/plain', status=200)
    else:
        return HttpResponse("User missmatch", mimetype='text/plain', status=403)


# member pages

@login_required
def dashboard(request):
    """
        Display applications owned by the current user.
        Include dependency info in the context!
    """

    if not utils.email_check(request):
        return HttpResponseRedirect(reverse('profiles_my_profile_detail'))

    # all apps by this user
    apps_data = {}
    for app in Application.objects.filter(
                                        owner=request.user.pk,
                                        status__gt=APP_STATUS_REMOVED
                                    ):
        apps_data[app.pk] = {
                                'pk' : app.pk,
                                'name' : app.name,
                                'url' : app.url,
                                'type_img_48_url' : app.type_img_48_url(),
                                'type' : app.type,
                                'status' : app.status,
                                'installed_versions' : set(),
                                # package count by status
                                'total' : 0,
                                'outdated' : 0,
                                'old' : 0,
                            }

    app_pks = apps_data.keys()
    installed_pvs = set() # PVs in use by all apps

    # get the number of total packages in each app
    for inst in InstalledPackage.objects.filter(
                                            application__in=app_pks
                                        ).only(
                                            'application',
                                            'version'
                                        ):
        apps_data[inst.application]['total'] += 1
        apps_data[inst.application]['installed_versions'].add(inst.version)
        installed_pvs.add(inst.version)

    advisories = {} # keys are PV.pk
    # number of LIVE updates for all different PVs
    for adv in Advisory.objects.filter(
                                        old__in=installed_pvs,
                                        status=STATUS_LIVE
                                    ).values(
                                        'old'
                                    ).annotate(
                                        Count('old')
                                    ):
        # how many updates were released for this PV
        advisories[adv['old']] = adv['old__count']

    outdated_pvs = advisories.keys()

    # now count how many PVs for each app are outdated
    for app in apps_data.keys():
        for pv in apps_data[app]['installed_versions']:
            if pv in outdated_pvs:
                apps_data[app]['outdated'] += 1


    # clear data which is not needed by the template
    # to minimize memory usage by the template engine
#todo: do we need this
    for app in apps_data.keys():
        apps_data[app]['installed_versions'] = None

    # transform as list
    template_data = []
    for app in apps_data.keys():
        template_data.append(apps_data[app])

    return render(
                request,
                'dashboard/apps2.html',
                {
                    'apps_data' : template_data,
                }
            )


@login_required
def ajax_invite_friends(request):
    """
        Send email invitation to friends
    """
    # we've got a POST request which means user wants to invite friends
    if request.POST:
        try:
            recipients = request.POST.get('recipients', "")

#todo: schedule batch action to offload main webserver
            for r in recipients.split("\n"):
                for addr in r.split(" "):
                    for email in addr.split(","):
                        try:
                            email = email.strip()
                            if email.find("@") == -1:
                                continue

                            send_templated_mail(
                                template_name='invite_friends',
                                from_email="Difio <%s>" % settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[email],
                                context={
                                    'username':request.user.username,
                                    'full_name':request.user.get_full_name(),
                                },
                            )
                        except:
                            continue
        except:
            pass

    return HttpResponse("SUCCESS", mimetype='text/plain')


def _appdetails_get_objects_fast(owner, app_id, show_all, page):   # FALSE NEGATIVE
    """
        @owner - int - Application.owner
        @app_id - int - Application.id
        @show_all - int - show all objects or updates only
        @page - int - page number when paging

        @return - dict - context to use in template
    """

    context = {
        'app' : None,
        'page_context' : None,
        'paginator_count' : None,
    }

    try:
        app = Application.objects.filter(pk=app_id, status__gt=APP_STATUS_PENDING, owner=owner)[0]
        context['app'] = app
    except IndexError:
        return context

    # subscriptions
    user = app.owner
    profile = user.get_profile()
    profile_is_subscribed = profile.is_subscribed()
    profile_plan_name = profile.get_subscription_plan_name()

    # store PKs, to be used later
    installed_pkgs_pks = set()
    installed_vers_pks = set()
    # keys are InstalledPackage.pk
    installed_pk_ver_pkg_map = {}

    query = InstalledPackage.objects.filter(
                                        application=app_id
                                    ).only(
                                        'version',
                                        'package'
                                    )

    # build PKs structures
    for inst in query:
        installed_pkgs_pks.add(inst.package)
        installed_vers_pks.add(inst.version)
        installed_pk_ver_pkg_map[inst.pk] = { 'v' : inst.version, 'p' : inst.package}

    # build a list of available updates
    # keys are PackageVersion.pk, where key is installed
    advisories = {}
    new_vers_pks = set() # PKs for new versions. Used to get version as string below

    one_week_ago = datetime.now() - timedelta(days=7)
    one_month_ago = datetime.now() - timedelta(days=30)


    query = Advisory.objects.filter(
                            old__in=installed_vers_pks,
                            status=STATUS_LIVE
                        ).only('new', 'old')

    # holds the PKs of installed packages for which
    # analytics are not yet LIVE. This is used in templates to
    # show the package is still being processed by the backend
    in_progress_query = Advisory.objects.filter(
                            old__in=installed_vers_pks,
                            status__gte=STATUS_NEW,
                            status__lt=STATUS_LIVE,
                        ).only('old')
    analytics_in_progress_for_inst_pkgs = set(adv.old_id for adv in in_progress_query)

    for adv in query:
        if not advisories.has_key(adv.old_id):
            advisories[adv.old_id] = []

        adv_tmp = {
                        'pk' : adv.pk,
                        'new_pk' : adv.new_id,
                    }
#todo: released_on dates are mapped below but we need the PK of the new packages as well
# move it above to disable JOINs
        advisories[adv.old_id].append(adv_tmp)
        new_vers_pks.add(adv.new_id)

    # store Package.name and PackageVersion.version
    # keys are Object.pk
    name_map = {}
    ver_map = {}
    released_on_map = {}

    # fetch package names
    for pkg in Package.objects.filter(pk__in=installed_pkgs_pks).only('name'):
        name_map[pkg.pk] = pkg.name


    # fetch installed and new package versions
    for ver in PackageVersion.objects.filter(pk__in=installed_vers_pks.union(new_vers_pks)).only('version', 'released_on'):
        ver_map[ver.pk] = ver.version
        released_on_map[ver.pk] = ver.released_on

    # map for which packages there are previous analytics
    previous_analytics_map = set()
    for analytic in Advisory.objects.filter(
                                        old__package__in=installed_pkgs_pks
                                    ).values(
                                        'old__package'
                                    ).annotate(
                                        count=Count('old__package')
                                    ).filter(count__gt=0):
        previous_analytics_map.add(analytic['old__package'])

    # build data structure for the template
    packages = []
    for inst_pk in installed_pk_ver_pkg_map.keys():
        inst_ver_pk = installed_pk_ver_pkg_map[inst_pk]['v']
        installed_released_on = released_on_map[inst_ver_pk]
        inst_pkg_pk = installed_pk_ver_pkg_map[inst_pk]['p']
        package_name = name_map[inst_pkg_pk]
        package_version = ver_map[inst_ver_pk]

        if advisories.has_key(inst_ver_pk):
            adv_objs = advisories[inst_ver_pk]
        else:
            adv_objs = []

        if show_all or adv_objs:
            date_adv_map = {}

            # add new versions and dates
            for adv in adv_objs:
                new_pk = adv['new_pk']
                adv['new'] = ver_map[new_pk]
                date  = released_on_map[new_pk]
                adv['date'] = date

                # HIDE analytics if package is relatively new and user has no appropriate subscription
                adv['url'] = Advisory.get_full_path_from_string(package_name, package_version, adv['new'], adv['pk'])
                adv['freshness'] = 'green'

                # package released during the last week
                if (one_week_ago <= adv['date']):
                    if (not profile_is_subscribed) or (profile_plan_name != 'Beaker'):
                        adv['freshness'] = 'gray'
                        adv['url'] = reverse('profiles_my_profile_detail')
                    else:
                        adv['freshness'] = 'red'

                # package released during the last month
                if (one_month_ago <= adv['date'] < one_week_ago):
                    if not profile_is_subscribed:
                        adv['freshness'] = 'gray'
                        adv['url'] = reverse('profiles_my_profile_detail')
                    else:
                        adv['freshness'] = 'orange'

                # some Ruby packages release multiple versions
                # in the same day and HH:MM:SS is not available
                if not date_adv_map.has_key(date):
                    date_adv_map[date] = []

                date_adv_map[date].append(adv)

            # sort versions by date
            dates = date_adv_map.keys()
            dates.sort(reverse=True)
            sorted_adv = []
            for d in dates:
                for adv in date_adv_map[d]:
                    sorted_adv.append(adv)

            data = {
                        'installed' : "%s-%s" % (package_name, package_version),
                        'installed_id' : inst_pk,
                        'advisories' : sorted_adv,
                        'in_progress' : inst_ver_pk in analytics_in_progress_for_inst_pkgs,
                    }
            if (not data['advisories']) and (not data['in_progress']) and \
                inst_pkg_pk in previous_analytics_map:
                data['previous'] = True
                data['name'] = package_name
                data['package_pk'] = inst_pkg_pk
            else:
                data['previous'] = False

            packages.append(data)

    # order by package name
    name_ver = {}
    for p in packages:
        name_ver[p['installed']] = p

    names = name_ver.keys()
    names.sort()

    packages = [] # clear because will be overriden below
    for n in names:
        packages.append(name_ver[n])


    if page == -1:
        # special case used by the email notification subsystem
        paginator = Paginator(packages, 1000000) # this should be big enough number
        page = 1 # then return the first and only page
    else:
        paginator = Paginator(packages, utils.VIEW_PAGINATOR)

    # If page request (9999) is out of range, deliver last page of results.
    try:
        page_context = paginator.page(page)
    except (EmptyPage, InvalidPage):
        page_context = paginator.page(paginator.num_pages)

    context['page_context'] = page_context
    context['paginator_count'] = len(page_context.object_list)

    return context


@login_required
def appdetails(request, id):
    """
        Display information about particular application.
    """
    # whether or not to show all packages or only these which need updates
    # by default will show only packages which need updates
    show_all = 1 # 2013-08-27 - always show all

    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        page = 1


    context = _appdetails_get_objects_fast(request.user.id, int(id), show_all, page)

    if context['app'] is None:
        messages.error(request, "Can see only your approved applications")
        return HttpResponseRedirect(reverse('dashboard'))

    context['show_all'] = show_all

    return render(request, 'apps/details.html', context)

@login_required
def previous_analytics(request, package, id):
    """
        Return a list of previous analytics for the given package.
        Only shows analytics which the user can access.
        Also limits to the last 100 of them!
    """
    context = []
    profile = request.user.get_profile()

#TODO: this code block needs to go into a separate method
# together with the cut-off logic in _appdetails_get_objects_fast()

    if profile.is_subscribed():
        if (profile.get_subscription_plan_name() == 'Beaker'):
            # show everything
            cut_off = datetime.now() 
        else:
            # show everything older than one week
            cut_off = datetime.now() - timedelta(days=7)
    else:
        # show everything older than one month
        cut_off = datetime.now() - timedelta(days=30)

#TODO: this query can be very slow if there are
# large number of previous analytics available
    for adv in Advisory.objects.filter(
                                    status=STATUS_LIVE,
                                    old__package=id,
                                    new__released_on__lte=cut_off,
                                ).order_by(
                                    '-new__released_on',
                                    '-old__released_on'
                                )[:100]:
        context.append(
            {
                'name' : adv.__unicode__(),
                'url'  : adv.get_full_path(),
            }
        )


    return render(
                request,
                'previous_analytics.html',
                {
                    'context' : context
                }
            )


@login_required
def mock_profile_details(request):
    """
        Just a mock view. Override with your own profile view
    """

    context = {
        'profile' : request.user.get_profile(),
    }

    return render(request, 'profiles/mock_profile_details.html', context)


@login_required
def app_history(request, id):
    """
        Display information about application history.
    """

    try:
        app = Application.objects.filter(pk=id, owner=request.user)[0]
    except IndexError:
        messages.error(request, 'Application not found')
        return HttpResponseRedirect(reverse('dashboard'))

    query = ApplicationHistory.objects.filter(application=id).order_by('-when_added')
    return render(request, 'apps/history.html', {'context' : query, 'app' : app })


def _application_manual_register(data, request, FormClass, form_field, template, parse_func, search_into_files=False):  # FALSE NEGATIVE
    """
        Manually register the application. Used as helper from views.

        @data - dict - application data used for registration
        @request - HttpRequest object
        @FormClass - class - the form to use
        @form_field - string - the name of the data field in the form
        @template - string - path to form template
        @parse_func - callback - function to parse the package list
        @search_into_files - bool - if True will check if any files were uploaded
                and will use form_field to access the files contents

        @return - HttpResponse
    """

    UUID = request.GET.get('uuid', '')

    if not request.POST:
        form = FormClass()
        return render(request, template, {'form': form, 'uuid': UUID })
    elif search_into_files and (not request.FILES):
        form = FormClass()
        return render(request, template, {'form': form, 'uuid': UUID })
    else:
        if search_into_files:
            form = FormClass(request.POST, request.FILES)
        else:
            form = FormClass(request.POST)

    if not form.is_valid():
        return render(request, template, {'form': form, 'uuid': UUID })

    if search_into_files:
        # b/c all functions take string and split by new line
        package_text = "\n".join(request.FILES[form_field])
    else:
        package_text = request.POST.get(form_field, "")

    if not package_text:
        messages.error(request, "Empty package list!")
        return render(request, template, {'form': form, 'uuid' : UUID })


    result = parse_func(request, package_text)

    if result['errors'] > 0:
        return render(request, template, {'form': form, 'uuid': UUID })

    # set common values
    data['user_id']    = request.user.id
    data['app_name']   = 'CHANGE ME'
    data['app_uuid']   = uuid.uuid4().__str__()
    data['app_url']    = 'http://example.com'
    data['app_vendor'] = VENDOR_MANUAL_IMPORT
    data['installed']  = result['packages']

    if UUID: # application has been imported previously
        data['app_uuid'] = UUID

    # register to DB
    response = application_register(request, import_data=data, skip_user=True)
    result = json.loads(response.content)

    if result['exit_code'] == 0:
        messages.success(request, result['message'])
        return HttpResponseRedirect(reverse('dashboard'))
    else:
        messages.error(request, result['message'])
        return render(request, template, {'form': form, 'uuid': UUID })



@login_required
def application_import_pip_freeze(request):
    """
        Allow the user to copy&paste the output of pip freeze and pass it to
        application_register()
    """
    data = {
        'app_type'   : 'python',
        'pkg_type'   : PYPI_PYTHON_PKG,
    }

    return _application_manual_register(data, request, PipFreezeForm, 'pipfreeze', 'import/pip-freeze.html', pkg_parsers.parse_pip_freeze)


@login_required
def application_import_bundle_list(request):
    """
        Manual Ruby import. Allow the user to copy&paste the output of
        `bundle list` or `gem list` and pass it to application_register()
    """
    data = {
        'app_type'   : 'ruby',
        'pkg_type'   : RUBYGEM_RUBY_PKG,
    }

    return _application_manual_register(data, request, BundleListForm, 'bundlelist', 'import/bundle-list.html', pkg_parsers.parse_bundle_list)


@login_required
def application_import_npm_ls(request):
    """
        Manual Node.js import. Allow the user to copy&paste the output of
        `npm ls` and pass it to application_register()
    """
    data = {
        'app_type'   : 'node.js',
        'pkg_type'   : NODEJS_PKG,
    }

    return _application_manual_register(data, request, NpmLsForm, 'npmls', 'import/npm-ls.html', pkg_parsers.parse_npm_ls)


@login_required
def application_import_perllocal(request):
    """
        Manual Perl import. Allow the user to upload the
        perllocal.pod file and pass it to application_register()
    """
    data = {
        'app_type'   : 'perl',
        'pkg_type'   : PERL_CPAN_PKG,
    }

    return _application_manual_register(data, request, PerlLocalForm, 'perllocal', 'import/perllocal.html', pkg_parsers.parse_perllocal, True)


@login_required
def application_import_maven(request):
    """
        Allow the user to copy&paste the output of `mvn dependency:list` and pass it to
        application_register()
    """
    data = {
        'app_type'   : 'java',
        'pkg_type'   : JAVA_MAVEN_PKG,
    }

    return _application_manual_register(data, request, MvnDependencyListForm, 'mvn', 'import/mvn-dependency-list.html', pkg_parsers.parse_mvn_dependency_list)


@login_required
def application_import_composer(request):
    """
        Allow the user to copy&paste the output of `./composer.phar show' and pass it to
        application_register()
    """
    data = {
        'app_type'   : 'php',
        'pkg_type'   : PHP_PACKAGIST_PKG,
    }

    return _application_manual_register(data, request, ComposerShowForm, 'composer', 'import/composer-show.html', pkg_parsers.parse_composer_show)


@ratelimit(block=True, rate='5/s')
@csrf_exempt
def application_register(request, import_data=None, skip_user=False):
    """
        @import_data - dictionary - used by other import methods
        @skip_user - used by other import methods

        Executed by external clients. POST data is in JSON format:
        json_data :
        {
            'user_id'    : integer,
            'app_name'   : string,
            'app_uuid'   : string,
            'app_type'   : string,
            'app_url'    : string,
            'app_vendor' : integer,
            'pkg_type'   : integer,
            'installed'  : list of {'n' : 'package name', 'v' : 'version', 't' : 'package type'}
        }

        Response is in JSON format:
        {
            'message' : string,
            'exit_code' : integer
        }

        exit_code non-zero is failure
    """
    def myresponse(message, exit_code=0, status=200):  # FALSE NEGATIVE
        """Helper function"""
        r = {'message' : message, 'exit_code' : exit_code}
        return HttpResponse(json.dumps(r)+"\n", mimetype='application/json', status=status)

#### view code starts here
    if import_data:
        data = import_data
    else:
        if not request.POST:
            return myresponse('Not a POST request', exit_code=1, status=400)

        data = json.loads(request.POST.get('json_data', ""))

    # SANITY CHECK INPUT VALUES
    for field in ['user_id', 'app_name', 'app_uuid', 'app_type', 'app_url', 'app_vendor', 'pkg_type', 'installed']:
        if (not data.has_key(field)) or (data[field] in [None, "", {}, []]):
            return myresponse("Invalid or missing field '%s'" % field, exit_code=1, status=400)

    # SANITY: user_id must be positive
    try:
        uid = int(data['user_id'])
        if uid <= 0:
            return myresponse("Invalid user id '%s'" % data['user_id'], exit_code=1, status=403)
    except:
        return myresponse("Invalid user id '%s'" % data['user_id'], exit_code=1, status=403)

    # SANITY: app_vendor must match particular values
    try:
        vendor = int(data['app_vendor'])
        if vendor not in [v[0] for v in VENDOR_TYPES]:
            return myresponse("Invalid vendor id '%s'" % data['app_vendor'], exit_code=1, status=400)
    except:
        return myresponse("Invalid vendor id '%s'" % data['app_vendor'], exit_code=1, status=400)

    # sanitize packages and versions
    for n_v_r in data['installed']:

        if n_v_r.has_key('t'):
            pkg_type = n_v_r['t']
        else:
            pkg_type = data['pkg_type']

        # SANITY: pkg_type must match particular values
        try:
            pkg_type = int(pkg_type)
            if pkg_type not in [p[0] for p in PACKAGE_TYPES]:
                return myresponse("Invalid pkg_type id '%d'" % pkg_type, exit_code=3, status=400)
        except:
            return myresponse("Invalid pkg_type id '%s'" % pkg_type, exit_code=3, status=400)

        # SANITY: both name and version must be present and not empty
        for key in ['n', 'v']:
            if not n_v_r.has_key(key):
                return myresponse("Missing required key '%s' for entry '%s'" % (key, str(n_v_r)), exit_code=4, status=400)
            elif n_v_r[key] in [None, ""]:
                return myresponse("Missing required value for entry '%s'" % str(n_v_r), exit_code=4, status=400)

    if skip_user:
        owner = request.user
    else:
        try: # find the user first
            owner = User.objects.filter(id=data['user_id']).only('id')[0]
        except IndexError:
            return myresponse("User with id '%s' not found" % data['user_id'], exit_code=2, status=403)

    # create the application object so there's something to show in the UI
    is_first_import = False
    is_manual_import = import_data is not None
    data['name_url_type_changed'] = False
    try:
        # search for application from this user
        app = Application.objects.filter(
                                    owner=owner.pk,
                                    status__gt=APP_STATUS_REMOVED,
                                    vendor=data['app_vendor'],
                                    uuid=data['app_uuid']
                                ).only(
                                    'pk',
                                    'name',
                                    'url',
                                    'type'
                                )[0]

        # in case of manual import name/url is CHANGE ME/example.com
        # if previously registered then keep what has been manually configured
        if is_manual_import and \
            ((app.name != data['app_name']) or (app.url != data['app_url'])):
            data['app_name'] = app.name
            data['app_url'] = app.url
            data['name_url_type_changed'] = True

        # this can also change but rarely
        if app.type != data['app_type']:
            data['name_url_type_changed'] = True

    except IndexError:  # first time registration - create an Application object
        # automated import
        is_first_import = True
        date_approved = None

        # if first-time manual importing always set to Approved
        if is_manual_import:
            date_approved = datetime.now()

        app = Application.objects.create(
                            owner_id=owner.pk,
                            status=APP_STATUS_IMPORTING,
                            vendor=data['app_vendor'],
                            uuid=data['app_uuid'],
                            name = data['app_name'],
                            type = data['app_type'],
                            url = data['app_url'],
                            last_checkin = datetime.now(),
                            date_approved = date_approved
                         )


    # using cache to pass the data parameter to avoid
    # reaching SQS message size limit
    task_cache = cache_module.get_cache('taskq')
    task_cache.set(data['app_uuid'], data, 3600) # 1hr

    difio.tasks.import_application.delay(app.pk, data['app_uuid'], owner.pk, is_manual_import, is_first_import)

    return myresponse('Success! Importing/updating your application!')


#################
#
# web hooks
#
#################

@csrf_exempt
def hook_rubygems(request):
    """
        Receive notification about new gems on Rubygems.org
    """


    if not request.POST:
        return HttpResponse("Not a POST", mimetype='text/plain', status=403)

    data = request.read()
    data = json.loads(data)

    authorization = hashlib.sha256(data['name'] + data['version'] + settings.RUBYGEMS_API_KEY).hexdigest()
    if request.META['HTTP_AUTHORIZATION'] != authorization:
        return HttpResponse("Unauthorized", mimetype='text/plain', status=401)
    else:
        try:
# see https://github.com/rubygems/rubygems.org/issues/536
            # todo: don't add prerelease software
            (latest_ver, released_on) = rubygems.get_latest(data['name']) # this can raise 404 sometimes

            if latest_ver == data['version']:
                difio.tasks.pv_import_new_from_rss.delay(RUBYGEM_RUBY_PKG, data['name'], data['version'], released_on)
        except:
            pass

    return HttpResponse("Success", mimetype='text/plain', status=200)

