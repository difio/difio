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


import re
import sys
import bugs
import utils
from models import *
import difio.tasks
from django.contrib import admin
from django.contrib import messages
from django.shortcuts import render
from buttons import ButtonableModelAdmin
from datetime import datetime, timedelta
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.core.files.base import ContentFile
from django.contrib.admin import SimpleListFilter
from django.core.handlers.wsgi import WSGIRequest
from django.contrib.auth.models import AnonymousUser
from github import _get_user_repo as github_get_user_repo


class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'uuid', 'vendor', 'status', 'last_checkin')
    list_filter = ('status', 'date_approved')
    search_fields = ['name', 'uuid']

class InstalledPackageListFilter(SimpleListFilter):
    """
        Filter Packages which are installed.
    """
    title = "Installed"
    parameter_name = 'is_installed'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
            ('0', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            q = InstalledPackage.objects.only('package').distinct()
            return queryset.filter(pk__in=set(inst.package for inst in q))
        else:
            # NB: if value is 0 it will always return ALL objects, not NON installed
            return queryset

class PackageAdmin(ButtonableModelAdmin):
    _list_url = '/admin/'
    _edit_url = '/admin/difio/package/%s/'

    list_display = ('name', 'status', 'latest_version', 'last_checked', 'type', 'website_html', 'scmtype', 'bugtype')
    list_filter = (InstalledPackageListFilter, 'status', 'type', 'scmtype', 'bugtype')

    def website_html(self, obj):
        return "<a href='%s'>%s</a>" % (obj.website, obj.website)
    website_html.allow_tags = True
    website_html.short_description = 'Website'
    website_html.admin_order_field = 'website'

    def name_type(self, obj):
        return "%s - %s" % (obj.name, obj.get_type_display())
    name_type.short_description = 'Name'

    def get_readonly_fields(self, request, obj=None):
        if request.user.has_perm('difio.package_modify_all'):
            return super(PackageAdmin, self).get_readonly_fields(request, obj)
        else:
            return ('name', 'status', 'assigned_to', 'website_link', 'scm_link',
                    'bug_link', 'type', 'last_checked', 'latest_version',
                    'name_type', 'added_on'
                    )

    def get_fieldsets(self, request, obj=None):
        if request.user.has_perm('difio.package_modify_all'):
            return super(PackageAdmin, self).get_fieldsets(request, obj)
        else:
            return (
                (None, {
                    'fields': (('name_type', 'status', 'assigned_to'), ('website', 'website_link'),
                                ('scmurl', 'scmtype', 'scm_link'), ('bugurl', 'bugtype', 'bug_link'),
                                'changelog', 'subpackage_path'
                                )
                        }
                ),
            )

    search_fields = ['name', 'assigned_to', 'website']
    save_on_top = True

    def website_link(self, obj):
        index_url = obj.index_url()
        return "<a href='%s'>%s</a>, <a href='%s'>%s</a> " % (obj.website, obj.website, index_url, index_url)
    website_link.allow_tags = True

    def scm_link(self, obj):
        """
            Display a HARD-CODED button link alongside the edit box.
        """
        url = reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.module_name), args=[obj.id])
        text = "<a href='%suse_tar/'>Use TAR</a>" % url
        if obj.type == PERL_CPAN_PKG:
             text += " | <a href='%suse_metacpan/'>Use MetaCPAN</a>" % url

        return text
    scm_link.allow_tags = True

    def bug_link(self, obj):
        """
            Display a HARD-CODED button link alongside the edit box.
        """
        url = reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.module_name), args=[obj.id])
        return "<a href='%sno_tracker/'>No Bug Tracker</a>" % url
    bug_link.allow_tags = True


    def find_site(request, id):
        Package.objects.filter(id=id).update(assigned_to=request.user.username)
        difio.tasks.cron_find_homepages.delay(id)
        messages.success(request, "Scheduled search for homepage!")
        return HttpResponseRedirect(PackageAdmin._list_url)
    find_site.short_description = 'FIND URL'

    def find_new_versions(request, id):
        Package.objects.filter(id=id).update(assigned_to=request.user.username)
        difio.tasks.cron_find_new_versions.delay(id, rate_limit=False)
        messages.success(request, "Scheduled search for new versions!")
        return HttpResponseRedirect(PackageAdmin._list_url)
    find_new_versions.short_description = 'FIND NEW'

    def use_tar(request, id):
        Package.objects.filter(id=id).update(scmtype=utils.SCM_TARBALL, assigned_to=request.user.username)
        Package.objects.filter(id=id, scmurl__isnull=True).update(scmurl="N/A")
        messages.success(request, "Will be using tarballs to generate diff/changelog!")
        return HttpResponseRedirect(PackageAdmin._edit_url % id)
    use_tar.short_description = 'TARBALL'

    def use_metacpan(request, id):
        # type and name used in index_url
        obj = Package.objects.filter(id=id).only('type', 'name')[0]
        if obj.type == PERL_CPAN_PKG:
            Package.objects.filter(id=id).update(scmtype=utils.SCM_METACPAN, scmurl=obj.index_url(), assigned_to=request.user.username)
            messages.success(request, "Will be using MetaCPAN to generate diff/changelog!")
        else:
            messages.warning(request, "MetaCPAN is only for Perl packages!")

        return HttpResponseRedirect(PackageAdmin._edit_url % id)
    use_metacpan.short_description = 'METACPAN'

    def no_tracker(request, id):
        Package.objects.filter(id=id).update(bugtype=bugs.BUG_TYPE_NONE, assigned_to=request.user.username)
        Package.objects.filter(id=id, bugurl__isnull=True).update(bugurl='http://example.com/%d')
        messages.success(request, "Bug tracker fields set!")
        return HttpResponseRedirect(PackageAdmin._edit_url % id)
    no_tracker.short_description = 'NO BUGS'

    buttons = [find_site, find_new_versions, use_tar, use_metacpan, no_tracker]

    def save_model(self, request, obj, form, change):
        ### additional helpers to speed up data entry
        obj.scmurl = utils.normalize_checkout_url(obj.scmurl) or utils.get_checkout_url(obj.website)
        obj.scmtype = utils.get_scm_type(obj.scmurl, obj.scmtype)

        obj.bugurl = bugs.normalize_bug_format_string(obj.bugurl) or bugs.get_bug_format_string(obj.website)
        obj.bugtype = bugs.get_bug_type(obj.bugurl, obj.bugtype)
        try:
            obj.changelog = obj.changelog or utils.get_changelog(obj.scmurl)
        except:
            pass

        ### end helpers

        # perform checks before moving to VERIFIED
        result = utils.test_if_package_verified(obj)

        # print any messages from the test
        for (msg_type, msg_text) in result['messages']:
            messages.add_message(request, msg_type, msg_text)

        obj.status = utils.get_status(result['scores'], utils.SCORES_PACKAGE_VERIFIED, STATUS_VERIFIED, STATUS_MODIFIED)

        if obj.status == STATUS_VERIFIED:
            messages.success(request, "All data successfully VERIFIED")
        elif obj.status == STATUS_MODIFIED:
            messages.warning(request, "Status is MODIFIED")

        obj.assigned_to = request.user.username
        if obj.status == STATUS_MODIFIED:
            obj.status = STATUS_ASSIGNED

        # NB: using this ugly .update() instead of save() because it allows for data partitioning
        # However object fields are set above to please the test_if_package_verified() function
        # so that it doesn't have to hit the DB again.
        Package.objects.filter(
                pk=obj.pk
            ).update(
                website = obj.website,
                scmurl = obj.scmurl,
                scmtype = obj.scmtype,
                bugurl = obj.bugurl,
                bugtype = obj.bugtype,
                changelog = obj.changelog,
                subpackage_path = obj.subpackage_path,
                status = obj.status
            )

class InstalledPackageVersionListFilter(SimpleListFilter):
    """
        Filter PVs which are installed.
    """
    title = "Installed"
    parameter_name = 'is_installed'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
            ('0', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == '1':
            q = InstalledPackage.objects.only('version').distinct()
            return queryset.filter(pk__in=set(inst.version for inst in q))
        else:
            # NB: if value is 0 it will always return ALL objects, not NON installed
            return queryset


class PackageVersionAdmin(ButtonableModelAdmin):
    _list_url = '/admin/'
    _edit_url = '/admin/difio/packageversion/%s/'

    list_display = ('name_version', 'apps_count', 'released_on', 'status', 'scmid', 'size', 'download_url')
    list_filter = (InstalledPackageVersionListFilter, 'status', 'package__type', 'package__scmtype', 'package__bugtype', 'assigned_to')


    def get_readonly_fields(self, request, obj=None):
        if request.user.has_perm('difio.packageversion_modify_all'):
            return super(PackageVersionAdmin, self).get_readonly_fields(request, obj)
        else:
            return ('package', 'package_status', 'version', 'status',
                    'assigned_to', 'size', 'download_link', 'github_iframe',
                    'added_on'
                    )

    def get_fieldsets(self, request, obj=None):
        if request.user.has_perm('difio.packageversion_modify_all'):
            return super(PackageVersionAdmin, self).get_fieldsets(request, obj)
        else:
            return [
                (None, {
                    'fields': ( ('package_status'),
                                ('released_on', 'scmid', 'download_url', 'download_link'),
                                'github_iframe',
                            )
                        }
                ),
            ]

    search_fields = ['package__name', 'version', 'scmid']
    save_on_top = True

    def name_version(self, obj):
        return "%s-%s" % (obj.package, obj.version)
    name_version.short_description = 'Name-Version'
    name_version.admin_order_field = 'package__name'

    def package_status(self, obj):
        url = reverse('admin:%s_%s_change' %(obj.package._meta.app_label, obj.package._meta.module_name),  args=[obj.package_id])
        text = """
<strong>%s</strong>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
%s-%s,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<a href='%s'>%s - <strong>%s</strong></a>,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
<strong>%s</strong> bytes,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
ASSIGNED TO %s""" % (obj.get_status_display(), obj.package.name,
                        obj.version, url, obj.package.get_type_display(),
                        obj.package.get_status_display(), obj.size,
                        obj.assigned_to
                    )
        return text.replace("\n", "") # https://code.djangoproject.com/ticket/19226#comment:15
    package_status.short_description = 'Package'
    package_status.allow_tags = True

    def download_link(self, obj):
        return "<a href='%s'>GET</a>" % obj.download_url
    download_link.short_description = ""
    download_link.allow_tags = True

    def apps_count(self, obj):
        """
            Count how many Apps have this PV *INSTALLED*

            @obj - PackageVersion
            @return - int
        """
        # NB: installed packages are deleted when app is deleted so this is a good estimate
        return InstalledPackage.objects.filter(version=obj.pk).count()
    apps_count.short_description = "Apps #"


    def github_iframe(self, obj):
        """
            Show a commit which contains the version change
            or all commits list for easier searching.
        """
        url = None
        if obj.package.scmurl.find('github.com') > -1:
            user_repo = github_get_user_repo(obj.package.scmurl)
            if obj.scmid not in [None, "", utils.TAG_NOT_FOUND]:
                url = "https://github.com/%s/commit/%s" % (user_repo, obj.scmid)
            else:
                url = "https://github.com/%s/commits" % user_repo

        if not url:
            return ""

        return """<a href="%s">%s</a><br />""" % (url, url)
    github_iframe.short_description = 'Upstream'
    github_iframe.allow_tags = True


    def find_date(request, id):
        PackageVersion.objects.filter(id=id).update(assigned_to=request.user.username)
        difio.tasks.cron_search_dates.delay(id)
        messages.success(request, "Scheduled search for dates!")
        return HttpResponseRedirect(PackageVersionAdmin._list_url)
    find_date.short_description = 'FIND DATE'

    def find_tag(request, id):
        PackageVersion.objects.filter(id=id).update(assigned_to=request.user.username)
        difio.tasks.pv_find_tags.delay(id, True) # search tags for all PVs for this Package
        messages.success(request, "Scheduled TAG search!")
        return HttpResponseRedirect(PackageVersionAdmin._list_url)
    find_tag.short_description = 'FIND TAG'

    def find_dl_url(request, id):
        PackageVersion.objects.filter(id=id).update(assigned_to=request.user.username)
        difio.tasks.cron_find_download_url.delay(id)
        messages.success(request, "Scheduled URL search!")
        return HttpResponseRedirect(PackageVersionAdmin._list_url)
    find_dl_url.short_description = 'FIND URL'

    buttons = [find_date, find_tag, find_dl_url]

    def save_model(self, request, obj, form, change):
        # flip ASSIGNED to MODIFIED after doing manual inspection
        # so that later we can change to VERIFIED
        if obj.status == STATUS_ASSIGNED:
            obj.status = STATUS_MODIFIED

        # perform checks before moving to VERIFIED
        result = utils.test_if_package_version_verified(obj)

        # print any messages from the test
        for (msg_type, msg_text) in result['messages']:
            messages.add_message(request, msg_type, msg_text)

        obj.status = utils.get_status(result['scores'], utils.SCORES_PACKAGE_VERSION_VERIFIED, STATUS_VERIFIED, STATUS_MODIFIED)

        if obj.status == STATUS_VERIFIED:
            messages.success(request, "All data successfully VERIFIED")
        elif obj.status == STATUS_MODIFIED:
            messages.warning(request, "Status is MODIFIED")

        obj.assigned_to = request.user.username
# NB: For PVs ASSIGNED is used only to indicate that manual inspection is needed
# not to indicate a user is working on this object record
#        if obj.status == STATUS_MODIFIED:
#            obj.status = STATUS_ASSIGNED


        # NB: using this ugly thing b/c test_if_package_version_verified needs an object
        # and we don't want to make it hit the DB again
        PackageVersion.objects.filter(
                pk=obj.pk
            ).update(
                status = obj.status,
                version = obj.version,
                scmid = obj.scmid,
                assigned_to = obj.assigned_to,
                released_on = obj.released_on,
                download_url = obj.download_url
            )


def check_advisory_validity(request, obj):
    from django.contrib.messages import constants as message_levels

    error_messages = []
    scores = 0

    # NB: Since 2012-04-20 this holds the change rate %
    if obj.type is None:
        error_messages.append((message_levels.ERROR, 'Change rate % not calculated!'))
    else:
        scores += 1

    if obj.severity == utils.SEVERITY_UNKNOWN:
        error_messages.append((message_levels.ERROR, "Severity is not set!"))
    else:
        scores += 1


    bugs_query = utils.get_bugs_query(obj.id)
    bugs_count = bugs_query.count()
    last_bug_number = None
    wrong_date_bugs = []
    bugs_404 = []
    fuzzy_match = False

    if bugs_count > 0:
        start_date = obj.old.released_on - timedelta(hours=24)
        end_date = obj.new.released_on + timedelta(hours=24)

        for bug in bugs_query:
            if bug.title.find('http://example.com') > -1:
                error_messages.append((message_levels.ERROR, "Bug list contains EXAMPLE.COM - fix with correct bug tracker URL!"))
                scores -= 1
#                break

            if bug.title.find('FAILED:') > -1:
                error_messages.append((message_levels.ERROR, "FAILED (404) found in bug list!"))
                bugs_404.append(bug.pk)
#                scores -= 1
                continue

            if bug.number == last_bug_number:
                bug.delete()
                error_messages.append((message_levels.ERROR, "Duplicate bug %d deleted!" % last_bug_number))
                continue # duplicates are deleted, don't search for dates
            else:
                last_bug_number = bug.number

            # bug has both dates => remove bugs which don't match release dates
            if (bug.reported_on is not None):
                if  (bug.reported_on > end_date) or \
                    (bug.closed_on is None) or \
                    (bug.closed_on < start_date) or (bug.closed_on > end_date):
                    wrong_date_bugs.append(bug.pk)
                    fuzzy_match = True
#                    error_messages.append((message_levels.ERROR, "Bug date mismatch for bug %d!" % bug.number))

        # see if we should remove all bugs due to wrong dates.
        # if all are to be removed then leave this to admin
        # otherwise remove them
        len_wrong_date_bugs = len(wrong_date_bugs)
        if (not fuzzy_match) or (0 < len_wrong_date_bugs < bugs_count):
            bugs_query.filter(pk__in=wrong_date_bugs).delete()
            error_messages.append((message_levels.ERROR, "%d bugs with wrong dates deleted!" % len_wrong_date_bugs))

        # always delete bugs which are 404s
        bugs_query.filter(pk__in=bugs_404).delete()
    else:
        error_messages.append((message_levels.WARNING, "No bugs list!"))


    # normal package or tarball for which scmid is not relevant
    if (obj.old.status == STATUS_VERIFIED) or \
        ((obj.old.status == STATUS_MODIFIED) and (obj.old.package.scmtype == utils.SCM_TARBALL)) or \
        ((obj.old.status >= STATUS_MODIFIED) and obj.overriden):
        scores += 1
    else:
        error_messages.append((message_levels.ERROR, "OLD is not VERIFIED!"))

    if (obj.new.status == STATUS_VERIFIED) or \
        ((obj.new.status == STATUS_MODIFIED) and (obj.new.package.scmtype == utils.SCM_TARBALL)) or \
        ((obj.new.status >= STATUS_MODIFIED) and obj.overriden):
        scores += 1
    else:
        error_messages.append((message_levels.ERROR, "NEW is not VERIFIED!"))

    if obj.old.released_on is None:
        error_messages.append((message_levels.ERROR, "OLD released_on is None"))
    else:
        scores += 1

    if obj.new.released_on is None:
        error_messages.append((message_levels.ERROR, "NEW released_on is None"))
    else:
        scores += 1

    if obj.old.package.status == STATUS_VERIFIED:
        scores += 1
    else:
        error_messages.append((message_levels.ERROR, "Package is not VERIFIED!"))

    if (obj.old.status == STATUS_VERIFIED) and (obj.new.status == STATUS_VERIFIED):
        if obj.overriden:
            error_messages.append((message_levels.ERROR, "VERIFIED but no commit log! Scheduled new diff!"))
            difio.tasks.generate_advisory_files.delay(obj.pk, ignore_status=True)
        else:
            scores += 1
    else:
        scores += 1

    if request is not None:
        # print any messages from the test
        for (msg_type, msg_text) in error_messages:
            messages.add_message(request, msg_type, msg_text)
    else: # print to stdout
        for (msg_type, msg_text) in error_messages:
            print msg_text


    return scores == 8

class AdvisoryAdmin(ButtonableModelAdmin):
    _list_url = '/admin/'
    _edit_url = '/admin/difio/advisory/%s/'

    list_display = ('old_new', 'affected_apps', 'status', 'package_type', 'released_on', 'last_updated', 
                    'old_status', 'new_status', 'package_status'
                    )
    list_filter = ('status', 'old__package__type', 'old__status', 'new__status',
                    'old__package__status', 'old__package__scmtype',
                    'old__package__bugtype', 'assigned_to'
                    )

    def get_readonly_fields(self, request, obj=None):
        if request.user.has_perm('difio.advisory_modify_all'):
            return super(AdvisoryAdmin, self).get_readonly_fields(request, obj)
        else:
            return ('old', 'new', 'old_new', 'status', 'assigned_to',
                    'details_html', 'package_link', 
                    'old_link', 'new_link', 'package_type', 'released_on',
                    'type', 'severity', 'overriden', 'status_html'
                    )

    def get_fieldsets(self, request, obj=None):
        if request.user.has_perm('difio.advisory_modify_all'):
            return super(AdvisoryAdmin, self).get_fieldsets(request, obj)
        else:
            return (
                (None, {
                    'fields': (('old_link', 'new_link', 'package_link', 'status_html', 'has_static_page'),
                                'details_html'
                              )
                        }
                ),
            )

    search_fields = ['old__package__name', 'old__version', 'new__version']
    save_on_top = True

    def package_type(self, obj):
        return obj.old.package.get_type_display()
    package_type.short_description='Package Type'
    package_type.admin_order_field = 'old__package__type'

    def affected_apps(self, obj):
        """
            Count how many apps will be affected for this advisory.

            @obj - Advisory
            @return - int
        """
        return InstalledPackage.objects.filter(version=obj.old_id).count()
    affected_apps.short_description = "Apps #"

    def old_new(self, obj):
        return "%s-%s" % (obj.old, obj.new)
    old_new.short_description = 'Name'
    old_new.admin_order_field = 'old__package__name'


    def details_html(self, obj):
        try:
            env = {
                'REQUEST_METHOD' : 'GET',
                'wsgi.input' : None,
            }
            request = WSGIRequest(env)
            request.user = AnonymousUser()
            bugstext = utils.get_bugs_as_html(obj.id, True)
            text = render(request, "apps/tabs.html", 
                            {
                                "advisory" : obj,
                                "bugs" : bugstext,
                                "is_admin" : 1,
                            }
                        )
            text = text.content
        except:
            text = "ERROR %s" % sys.exc_info()[1]
        # in Django 1.5 and later this is rendered as
        # <p>{{ field.contents|linebreaksbr }}</p>
        # which replaces newlines with <br /> tags and breaks formatting
        # https://code.djangoproject.com/ticket/19226#comment:15
        text = text.replace("\n", "")
        return text
    details_html.allow_tags = True
    details_html.short_description = ''

    def old_link(self, obj):
        url = reverse('admin:%s_%s_change' %(obj.old._meta.app_label, obj.old._meta.module_name),  args=[obj.old_id])
        return "<a href='%s'>%s-%s-%s</a>" % (url, obj.old, obj.old.get_status_display(), obj.old.size)
    old_link.short_description = 'O'
    old_link.allow_tags = True

    def new_link(self, obj):
        url = reverse('admin:%s_%s_change' %(obj.new._meta.app_label, obj.new._meta.module_name),  args=[obj.new_id])
        return "<a href='%s'>%s-%s-%s</a>" % (url, obj.new, obj.new.get_status_display(), obj.new.size)
    new_link.short_description = 'N'
    new_link.allow_tags = True

    def package_link(self, obj):
        url = reverse('admin:%s_%s_change' %(obj.old.package._meta.app_label, obj.old.package._meta.module_name),  args=[obj.old.package_id])
        return "<a href='%s'>%s - %s</a>" % (url, obj.old.package.get_type_display(), obj.old.package.get_status_display())
    package_link.short_description = 'P'
    package_link.allow_tags = True

    def old_status(self, obj):
        return obj.old.get_status_display()
    old_status.admin_order_field = 'old__status'
    old_status.short_description = 'Old status'

    def new_status(self, obj):
        return obj.new.get_status_display()
    new_status.admin_order_field = 'new__status'

    def package_status(self, obj):
        return obj.old.package.get_status_display()
    package_status.admin_order_field = 'old__package__status'

    def status_html(self, obj):
        s = obj.get_status_display()
        if obj.status == STATUS_LIVE:
            s = "<a href='%s'>%s</a>" % (obj.get_full_path(), s)
        return s
    status_html.admin_order_field = 'status'
    status_html.short_description = 'S'
    status_html.allow_tags = True

    def released_on(self, obj):
        return obj.new.released_on
    released_on.admin_order_field = 'new__released_on'
    released_on.short_description = 'Released On'

    def drop(request, id):
        if request.user.has_perm('difio.advisory_drop'):
            affected = Advisory.objects.filter(id=id).update(status=STATUS_DROPPED)
            if affected:
                messages.success(request, "Advisory DROPPED!")
                return HttpResponseRedirect(AdvisoryAdmin._list_url)
            else:
                messages.error(request, "ERROR!")
                return HttpResponseRedirect(AdvisoryAdmin._edit_url % id)
        else:
            messages.warning(request, "Can't DROP, not allowed!")
            return HttpResponseRedirect(AdvisoryAdmin._edit_url % id)
    drop.short_description = 'DROP'

    def push_ready(request, id):
        obj = Advisory.objects.filter(pk=id)[0] # check_advisory_validity will access all fields
        url = AdvisoryAdmin._list_url

        if obj.status >= STATUS_PUSH_READY:
            url = reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.module_name), args=[obj.id])
            messages.error(request, "Can't change to PUSH_READY anymore!")
        elif check_advisory_validity(request, obj):
            Advisory.objects.filter(pk=obj.pk).update(status=STATUS_PUSH_READY)
            messages.success(request, "Moved to PUSH_READY")
        else:
            url = reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.module_name), args=[obj.id])
            messages.error(request, "Moving to PUSH_READY failed!")

        return HttpResponseRedirect(url)
    push_ready.short_description = 'PUSH READY'

    def generate_diff(request, id):
        """
            Schedule diff using Git.
        """
        Advisory.objects.filter(id=id).update(status=STATUS_ASSIGNED, assigned_to=request.user.username)
        difio.tasks.generate_advisory_files.delay(id, ignore_status=True)
        messages.success(request, "Scheduled diff task!")
        return HttpResponseRedirect(AdvisoryAdmin._list_url)
    generate_diff.short_description = 'NEW DIFF'

    def diff_tar(request, id):
        """
            Schedule a diff but use tarballs instead of Git.
        """
        Advisory.objects.filter(id=id).update(status=STATUS_ASSIGNED, assigned_to=request.user.username)
        difio.tasks.generate_advisory_files.delay(id, ignore_status=True, override=True)
        messages.success(request, "Scheduled diff task!")
        return HttpResponseRedirect(AdvisoryAdmin._list_url)
    diff_tar.short_description = 'DIFF TAR'

    def find_bugs(request, id):
        Advisory.objects.filter(id=id).update(status=STATUS_ASSIGNED, assigned_to=request.user.username)
        difio.tasks.find_bugs.delay(id)
        messages.success(request, "Scheduled FIND BUGS task!")
        return HttpResponseRedirect(AdvisoryAdmin._list_url)
    find_bugs.short_description = 'FIND_BUGS'

    buttons = [push_ready, generate_diff, diff_tar, drop]

    def save_model(self, request, obj, form, change):
        if obj.status == STATUS_MODIFIED:
            obj.status = STATUS_ASSIGNED

        if check_advisory_validity(request, obj):
            messages.success(request, "Advisory can safely be moved to PUSH_READY")
        else:
            obj.status = STATUS_ASSIGNED

        Advisory.objects.filter(
                pk=obj.pk
            ).update(
                assigned_to = request.user.username,
                last_updated = datetime.now(),
                status = obj.status,
                overriden = obj.overriden,
                has_static_page = obj.has_static_page
            )

class ApplicationHistoryAdmin(admin.ModelAdmin):
    list_display  = ('application', 'when_added', 'comments')
    search_fields = ['application__name', 'application__owner__username']

class BugAdmin(admin.ModelAdmin):
    list_display  = ('advisory', 'number', 'title')
    search_fields = ['advisory__old__package__name', 'number', 'title']

admin.site.register(Application, ApplicationAdmin)
admin.site.register(Package, PackageAdmin)
admin.site.register(PackageVersion, PackageVersionAdmin)
admin.site.register(Advisory, AdvisoryAdmin)
admin.site.register(ApplicationHistory, ApplicationHistoryAdmin)
admin.site.register(Bug, BugAdmin)
