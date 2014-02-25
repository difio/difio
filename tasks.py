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
import sys
import api
import bugs
import json
import pypi
import time
import urls
import shlex
import utils
import views
import shutil
import github
import socket
import metacpan
import analytics
import bitbucket
import xmlrpclib
import subprocess
import mavencentral
from models import *
from time import sleep
from decorators import *
import distutils.dir_util
import distutils.file_util
from tar import bz2compress
from tempfile import mkdtemp
from celery.task import task
from traceback import format_tb
from django.conf import settings
from django.core.cache import cache
from django.core import cache as cache_module
from django.db import reset_queries
from django.shortcuts import render
from django.utils.html import escape
from django.db.models import Count, Q
from django.core.mail import send_mail
from htmlmin.minify import html_minify
from BeautifulSoup import BeautifulSoup
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.files.base import ContentFile
from templated_email import send_templated_mail
from django.core.handlers.wsgi import WSGIRequest
from django.contrib.auth.models import AnonymousUser
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, InvalidPage, EmptyPage

@task
def cron_find_homepages(id = None):
    """
        @id - integer - Package.id if specified.

        Looks for new packages and automatically tries to assign URL.
        Executed by CRON.
    """
    logger = cron_find_homepages.get_logger()

    logger.info("Going to search for homepages")

    query = Package.objects

    # if ID is specified search only this package
    if id is not None:
        query = query.filter(pk=id)
    else: # otherwise search only NEW packages
        # DON'T search URLs for Packages checked in the last 7 days
        last_time = datetime.now()-timedelta(days=7)
        query = query.filter(status=STATUS_NEW, last_checked__lte=last_time)
        # select only installed packages
        query = query.filter(pk__in=set(inst.package for inst in InstalledPackage.objects.only('package').distinct()))

    query = query.only('name', 'type')

    for pkg in query:
        try:
            # get a version object b/c some URLs require name and version
            # this is a quick hack to take the most recent version as sorted by the DB
            # it will not always be the most recent one, but should work well enough to populate
            # URLs into the DB.
            ver = PackageVersion.objects.filter(package=pkg.pk).only('version').order_by('-version')[0]
            find_homepage_for_package.delay(pkg.pk, pkg.name, ver.version, PACKAGE_CALLBACKS[pkg.type]['get_url'])
        except:
            logger.error("Can't find homepage for package: %s - %d" % (pkg.name, pkg.pk))
            logger.error("Exception: %s" % sys.exc_info()[1])
            logger.error(format_tb(sys.exc_info()[2]))
            continue

    reset_queries()


@task
def find_homepage_for_package(id, name, version, get_url_func):
    """
        Updates URL of particular Package.
        Not to be executed by CRON directly.

        @id - integer - Package object id
        @name - string - package name - used for performance reasons
        @version - string - package version - used for performance reasons
        @get_url_func - callback which returns the homepage URL
    """
    logger = find_homepage_for_package.get_logger()

    logger.info("Going to search for package URLs for %s" % name)

    try:
        urls = get_url_func(name, version)

        # additional helpers to speed up data entry
        website = urls['homepage']
        scm_url = utils.normalize_checkout_url(urls['repository']) or utils.get_checkout_url(website)
        scm_type = utils.get_scm_type(scm_url)
        bug_url = bugs.normalize_bug_format_string(urls['bugtracker']) or bugs.get_bug_format_string(website)
        bug_type = bugs.get_bug_type(bug_url)
        try:
            changelog = utils.get_changelog(scm_url)
        except:
            changelog = None
            logger.error("Exception: %s" % sys.exc_info()[1])
            logger.error(format_tb(sys.exc_info()[2]))

        Package.objects.filter(pk=id).update(website=website,
                                             scmurl=scm_url,
                                             scmtype=scm_type,
                                             bugurl=bug_url,
                                             bugtype=bug_type,
                                             changelog=changelog,
                                             status=STATUS_MODIFIED
                                            )

        logger.info("Updated website for %s" % name)

        # NB: no need to schedule as separate task. Minimize messages count
        move_package_to_verified(id)
    except:
        logger.error("Exception: %s" % sys.exc_info()[1])
        logger.error(format_tb(sys.exc_info()[2]))

    reset_queries()

@task
def move_package_to_verified(id):
    """
        Try and move the package to VERIFIED.

        @id - Package ID
    """
    logger = move_package_to_verified.get_logger()

    try:
        # test_if_package_verified will access all fields
        obj = Package.objects.filter(pk=id)[0]
    except IndexError:
        reset_queries()
        return

    if (obj.status >= STATUS_VERIFIED):
        return

    result = utils.test_if_package_verified(obj)
    status = utils.get_status(result['scores'], utils.SCORES_PACKAGE_VERIFIED, STATUS_VERIFIED, obj.status)
    Package.objects.filter(pk=obj.pk).update(status=status)

    logger.info("Moved Package %s to VERIFIED" % obj.name)
    reset_queries()


@task
def cron_find_new_versions(id = None, app_id = None, rate_limit = True):
    """
        @id - integer - Package.id - search new versions for this one package.
        @app_id - Application.id - search new versions only for packages linked to this app.
        @rate_limit - bool - don't search too often

        Search for new versions of packages.
        Executed by CRON.
    """
    logger = cron_find_new_versions.get_logger()

    logger.info("Going to search for new package versions")

    # search new versions for packages not checked in 20 hours
    last_time = datetime.now()-timedelta(hours=20)

    # select PackageVersion's followed/installed by users
    pv_ids = InstalledPackage.objects.only('version').distinct()

    # if app_id is not None then user pressed the
    # 'search updates' button in the apps view
    if app_id is not None:
        pv_ids = pv_ids.filter(application=app_id)

    # now select the objects themselves
    query = PackageVersion.objects.filter(
                pk__in=set(inst.version for inst in pv_ids)
            ).only('package')

    # if ID param was specified then
    # search new versions only for installed packages of
    # this Package object
    if id is not None:
        query = query.filter(package=id)


    for pv in query:
        try:
            pkg = Package.objects.filter(pk=pv.package_id).only('name', 'type', 'last_checked')[0]

            # impose date(rate) limit to avoid users
            # scheduling too often (via the website) to find updates.
            if rate_limit and pkg.last_checked and (pkg.last_checked > last_time):
                continue

            find_new_version_for_package.delay(
                                pv.pk,
                                pkg.name,
                                PACKAGE_CALLBACKS[pkg.type]['get_latest']
                            )
        except:
            logger.error("Exception: %s" % sys.exc_info()[1])
            logger.error(format_tb(sys.exc_info()[2]))
            continue

    reset_queries()


@task
def find_new_version_for_package(id, name, get_upstream_func):
    """
        Search for new versions of a particular package and create new objects.
        Not to be executed by CRON directly.

        @id - integer - PackageVersion object id
        @name - string - package name - used for performance reasons
        @get_upstream_func - callback to get the latest upstream version
    """

    logger = find_new_version_for_package.get_logger()

    logger.info("Going to search new versions for %s" % name)

    try:
        # currently installed version into an application (passed as parameter by cron)
        # NB: exception will be caught and logged via the outher try/except
        installed = PackageVersion.objects.filter(id=id)[0]

        # fetch latest version from upstream package source
        try:
            upstream_ver, upstream_released_on = get_upstream_func(name, installed.package.last_checked)
        except:
            # if search for upstream failed (happens for some MetaCPAN packages)
            # simulate 304 Not Modified, which will search the DB for the latest package
            # and generate advisory. This for example happened for CPAN's Test::TCP
            upstream_ver = 304
            upstream_released_on = 304

        # if we can't find version/date (e.g. wrong import)
        if not (upstream_ver or upstream_released_on):
            return

        # GET returned 304 Not Modified => get the latest PV available in DB
        if (upstream_ver == 304) and (upstream_released_on == 304):
            pv_upst = PackageVersion.objects.filter(package=installed.package).order_by('-released_on')[0]
        else:
            try:
                # this version is already present
                pv_upst = PackageVersion.objects.filter(package=installed.package, version=upstream_ver)[0]
            except IndexError:
                # create new PV object
                pv_upst = PackageVersion.objects.create(package=installed.package, version=upstream_ver, released_on=upstream_released_on)
                logger.info("Found new version %s-%s" % (name, upstream_ver))


        # NB: don't delay here
        # NB: this will call set_package_latest_version()
        # NB: always execute, not only for new PVs to catch the situation
        # where older package is installed *AFTER* the new one has been imported
        compare_versions_and_create_advisory(installed, pv_upst)

    except:
        logger.error("Exception: %s" % sys.exc_info()[1])
        logger.error(format_tb(sys.exc_info()[2]))

    reset_queries()

@task
def set_package_latest_version(installed, upstream):
    """
        Mark which version is latest for Package.latest_version

        @installed - PV object
        @upstream - PV object
    """
    # no latest_version for the package recorded (e.g. first time check)
    # or upstream.version > installed.package.latest_version (e.g. new upstream package found)
    # then update the database
    if (not installed.package.latest_version) or                  \
        (utils.ver_date_cmp(                                      \
                    upstream.version, upstream.released_on,       \
                    installed.package.latest_version, installed.released_on,      \
                    PACKAGE_CALLBACKS[installed.package.type]['compare_versions'] \
                ) > 0):
        Package.objects.filter(id=installed.package.id).update(latest_version=upstream.version)

@task
def compare_versions_and_create_advisory(installed, upstream):
    """
        Given two versions compare them and create advisory if needed.

        @installed - installed PV
        @upstream - newly found PV which supposedly is the latest version
    """
    logger = compare_versions_and_create_advisory.get_logger()
    logger.info("Will compare %s and %s" % (installed, upstream))

    # if date is missing and we don't know how to compare we end up with
    # advisories comparing the same package, b/c date comparison always
    # says the later version is newer and leaves it up to admin to filter out bugs
    if installed.pk == upstream.pk:
        # update this package so it's not checked again very soon
        Package.objects.filter(pk=installed.package_id).update(last_checked=datetime.now())
        return

    # if installed has no released_on date (e.g. newly imported package)
    # then try to find date because version compare will fail otherwise
    # NB: No delay here.
    if not installed.released_on:
        pv_find_date(installed.id, PACKAGE_CALLBACKS[upstream.package.type]['find_date'])
        installed = PackageVersion.objects.filter(pk=installed.pk)[0] # reload the object after date has been updated

    # bump the latest version marker
    set_package_latest_version(installed, upstream)

    older = None
    newer = None

    # compare versions
    result = utils.ver_date_cmp(upstream.version, upstream.released_on,
                                installed.version, installed.released_on,
                                PACKAGE_CALLBACKS[installed.package.type]['compare_versions']
                            )

    # upstream.version > installed.version
    if result > 0:
        older = installed
        newer = upstream

    # upstream.version < installed.version (e.g. bzr beta versions)
#    if result < 0:
#todo: add beta column
#        installed.is_beta = True
#        installed.save () # NB: dont' use .save use .update if enabled

# Don't create advisories for Beta packages
#        older = upstream
#        newer = installed

    # upstream.version != installed.version => create an advisory if not present
    if older and newer:
        try:
            advisory = Advisory.objects.filter(old=older, new=newer).only('id')[0]
        except IndexError:
            advisory = Advisory.objects.create(old=older, new=newer, last_updated=datetime.now())
            logger.info("Created new advisory for %s-%s-%s" % (older.package.name, older.version, newer.version))

            # try to pupulate missing data. Will move to VERIFIED if all found
            # NB: automatically collect data only if new advisory is created.
            # otherwise it's not needed so no need to send additional messages and get charged
#NB: no .delay()

            if not installed.package.scmurl:
                cron_find_homepages(installed.package.pk)
                sleep(10) # give it time to find some URLs

            if not installed.released_on:
                pv_find_date(installed.id, PACKAGE_CALLBACKS[installed.package.type]['find_date'])

            if (not installed.scmid) or (installed.scmid == utils.TAG_NOT_FOUND):
                pv_find_tags(installed.id, False) # no recursion, only this version

            if not installed.download_url:
                pv_find_download_url(installed.id, PACKAGE_CALLBACKS[installed.package.type]['get_download_url'])

            if not upstream.released_on:
                pv_find_date(upstream.id, PACKAGE_CALLBACKS[upstream.package.type]['find_date'])

            if (not upstream.scmid) or (upstream.scmid == utils.TAG_NOT_FOUND):
                pv_find_tags(upstream.id, False) # no recursion, only this version

            if not upstream.download_url:
                pv_find_download_url(upstream.id, PACKAGE_CALLBACKS[upstream.package.type]['get_download_url'])

    # update this package so it's not checked again very soon
    Package.objects.filter(pk=installed.package_id).update(last_checked=datetime.now())
    reset_queries()

@task
def cron_import_new_versions_from_rss():
    """
        Executed by CRON every hour. 
        Fetch RSS feeds about new packages and import them into DB.
        If any user has the same package installed then create an advisory.
    """
    logger = cron_import_new_versions_from_rss.get_logger()
    logger.info("Going to import latest packages from RSS")

    for pkg_type in PACKAGE_CALLBACKS.keys():
        get_latest_from_rss_func = PACKAGE_CALLBACKS[pkg_type]['get_latest_packages_from_rss']

        # NB: see note for Ruby in models.py
        if not get_latest_from_rss_func:
            continue

        pv_import_same_pkg_type_from_rss.delay(pkg_type, get_latest_from_rss_func)

    reset_queries()


@task
def pv_import_same_pkg_type_from_rss(pkg_type, get_latest_from_rss_func):
    """
        Helper to import all new packages from RSS for a particular package type
        e.g. Python, Perl, etc. Used to minimize message count.

        @pkg_type - int - what package type is this
        @get_latest_from_rss_func - callback - a func to get all the packages
    """

    for (name, version, released_on) in get_latest_from_rss_func():
        pv_import_new_from_rss(pkg_type, name, version, released_on) # NB: no .delay()
        time.sleep(2) # introduce some delay to offload DB server


@task
def pv_import_new_from_rss(pkg_type, name, version, released_on):
    """
        Create new Package/PackageVersion objects from name/version
        taken from RSS feeds. This should not be executed directly.

        @pkg_type - package type
        @name - package name
        @version - package version
        @released_on - date on which this PV was released (if available).
    """
    logger = pv_import_new_from_rss.get_logger()
    logger.info('Will import new package')

    try:
        package = Package.objects.filter(name=name, type=pkg_type)[0]
        is_new_package = False
    except IndexError:
        package = Package.objects.create(name=name, type=pkg_type)
        is_new_package = True

    try:
        pv = PackageVersion.objects.filter(package=package, version=version)[0]
    except IndexError:
        pv = PackageVersion.objects.create(package=package, version=version, released_on=released_on)
        logger.info("Imported new PV: %s" % pv)

        # search URLs now, after at least one version is imported
        # fails otherwise b/c no versions exist
# disabled: executed in compare_versions_and_create_advisory()
#        if is_new_package:
#            cron_find_homepages(package.id) # NB: no delay


        if not released_on:
            # NB: NO DELAY HERE b/c there's a race condition between pv_find_date() and
            # ver_date_cmp() in compare_versions_and_create_advisory() below if delayed
            pv_find_date(pv.id, PACKAGE_CALLBACKS[pv.package.type]['find_date'])

        # this is newly imported PV. It's possible that our users have an old
        # version installed. => Fetch all installed versions and generate advisories.
        # Select PVs which are followed/installed
        pv_ids = InstalledPackage.objects.filter(
                                        package=package.pk,
                                        version__gt=0,
                                    ).only('version').distinct()

        for installed in PackageVersion.objects.filter(pk__in=set(inst.version for inst in pv_ids)):
            # don't delay
            compare_versions_and_create_advisory(installed, pv)

    reset_queries()


@task
def cron_generate_advisory_files():
    """
        Create new Advisory files.
        Executed by CRON.
    """
    logger = cron_generate_advisory_files.get_logger()
    logger.info("Diffing new advisories")

    last_time = datetime.now()-timedelta(hours=1, minutes=30)
    query = Advisory.objects.filter(status=STATUS_NEW).only('pk')
    for adv in query:
        try:
            # try to pupulate missing data. Will move to VERIFIED if all found
            # NB: automatically collect data only if new advisory is created.
            # otherwise it's not needed so no need to send additional messages and get charged
#NB: no .delay()

            if not adv.old.package.scmurl:
                cron_find_homepages(adv.old.package.pk)
                sleep(10) # give it time to find some URLs

            if not adv.old.released_on:
                pv_find_date(adv.old.pk, PACKAGE_CALLBACKS[adv.old.package.type]['find_date'])

            if (not adv.old.scmid) or (adv.old.scmid == utils.TAG_NOT_FOUND):
                pv_find_tags(adv.old.pk, False) # no recursion, only this version

            if not adv.old.download_url:
                pv_find_download_url(adv.old.pk, PACKAGE_CALLBACKS[adv.old.package.type]['get_download_url'])

            if not adv.new.released_on:
                pv_find_date(adv.new.pk, PACKAGE_CALLBACKS[adv.new.package.type]['find_date'])

            if (not adv.new.scmid) or (adv.new.scmid == utils.TAG_NOT_FOUND):
                pv_find_tags(adv.new.pk, False) # no recursion, only this version

            if not adv.new.download_url:
                pv_find_download_url(adv.new.pk, PACKAGE_CALLBACKS[adv.new.package.type]['get_download_url'])

            # found what we could, now generate analytics

            if (adv.old.status == STATUS_VERIFIED) and (adv.new.status == STATUS_VERIFIED):
                generate_advisory_files.delay(adv.pk)
            elif (adv.last_updated <= last_time) and  (STATUS_NEW not in [adv.old.status, adv.new.status]):
                generate_advisory_files.delay(adv.pk, override=True)

        except:
            logger.error("Exception: %s" % sys.exc_info()[1])
            logger.error(format_tb(sys.exc_info()[2]))
            continue

    reset_queries()


def _compress_data_if_needed(data, path, field_name):
    if len(data) > utils.MYSQL_MAX_PACKET_SIZE:
        filename = '%s%s.txt.bz2' % (path, field_name)
        default_storage.save(filename, ContentFile(bz2compress(data)))
#NB: this will raise exception if default_storage is not on S3 (missing the url() method)
        url = default_storage.url(filename)

        # in case we're using S3 with protocol relative URLs
        if url.startswith('//'):
            url = 'http:' + url

        data = utils.INFO_DATA_TOO_BIG % url + "\n\n" + data[:utils.MYSQL_MAX_PACKET_SIZE]

    return data

@task
def generate_advisory_files(id, ignore_status=False, override=False):
    """
        Generate advisory files.
        Not to be executed by CRON directly.

        @id - integer - Advisory object id
        @ignore_status - bool - If set will diff regardless of status. Used for manual execution from Admin site.
    """
    logger = generate_advisory_files.get_logger()

    logger.info("Diffing new advisories")

    try:
        # additional fields will be fetched below.
        # big text fields will not be fetched because they are write-only in this method
        adv = Advisory.objects.filter(id=id).only('id', 'status')[0]
    except IndexError:
        reset_queries()
        return

    if (not ignore_status) and (adv.status >= STATUS_MODIFIED):
        return

    # mark IN PROGRESS
    Advisory.objects.filter(pk=adv.pk).update(status=STATUS_ASSIGNED, last_updated = datetime.now())

    cmdline = ""
    tmpdir = utils.which_tmp_dir()

    try:
        pkg_scm_type = adv.old.package.scmtype
        if override:
            pkg_scm_type = utils.SCM_TARBALL

        dirname = utils.which_checkout_dir(SCM_SHORT_NAMES[pkg_scm_type],      adv.old.package.type, adv.old.package.name, adv.pk)
        tardir  = utils.which_checkout_dir(SCM_SHORT_NAMES[utils.SCM_TARBALL], adv.old.package.type, adv.old.package.name, adv.pk)
        apidir  = utils.which_checkout_dir(SCM_SHORT_NAMES[utils.SCM_APIGEN],  adv.old.package.type, adv.old.package.name, adv.pk)
        magicdir= utils.which_checkout_dir(SCM_SHORT_NAMES[utils.SCM_MAGIC],   adv.old.package.type, adv.old.package.name, adv.pk)

        # prepare tarball and API directories
        utils.checkout_or_pull(tardir, adv.old.package.scmurl, SCM_CLONE_CMD[utils.SCM_TARBALL], SCM_PULL_CMD[utils.SCM_TARBALL])
        utils.checkout_or_pull(apidir, adv.old.package.scmurl, SCM_CLONE_CMD[utils.SCM_APIGEN], SCM_PULL_CMD[utils.SCM_APIGEN])
        utils.checkout_or_pull(magicdir, adv.old.package.scmurl, SCM_CLONE_CMD[utils.SCM_APIGEN], SCM_PULL_CMD[utils.SCM_APIGEN]) # just git init

        version_old = adv.old.scmid
        version_new = adv.new.scmid
        changelog_file = adv.old.package.changelog

        # download, untar and commit to local git repo if tarball
        # the repo is initialized above with the CLONE_CMD
        utils.download_extract_commit(adv.old, tardir, adv.old.package.type == PHP_PEAR_PKG)
        api_was_generated = False
        for r in api.generate_anything_from_source(adv.old, tardir, apidir, api.api_gen_callback): # API
            api_was_generated = api_was_generated or r
        old_filetypes = api.generate_anything_from_source(adv.old, tardir, magicdir, analytics.filetype_gen_callback) # file types
        old_filetypes = analytics.normalize_list_of_dict_into_dict(old_filetypes)
        # count the tests. Use temp dir, nothing will be written there except empty git repo
        old_tests = api.generate_anything_from_source(adv.old, tardir, mkdtemp(prefix='test_count_old_', dir=tmpdir), analytics.test_case_count_callback)
        # Get file sizes. Use temp dir, nothing will be written there except empty git repo
        sizes_old = api.generate_anything_from_source(adv.old, tardir, mkdtemp(prefix='size_old_', dir=tmpdir), analytics.file_size_callback)
        sizes_old = analytics.normalize_list_of_dict_into_dict(sizes_old)

        utils.download_extract_commit(adv.new, tardir, adv.new.package.type == PHP_PEAR_PKG)
        for r in api.generate_anything_from_source(adv.new, tardir, apidir, api.api_gen_callback): # API
            api_was_generated = api_was_generated or r
        new_filetypes = api.generate_anything_from_source(adv.new, tardir, magicdir, analytics.filetype_gen_callback) # file types
        new_filetypes = analytics.normalize_list_of_dict_into_dict(new_filetypes)
        # count the tests. Use temp dir, nothing will be written there except empty git repo
        new_tests = api.generate_anything_from_source(adv.new, tardir, mkdtemp(prefix='test_count_new_', dir=tmpdir), analytics.test_case_count_callback)
        # Get file sizes. Use temp dir, nothing will be written there except empty git repo
        sizes_new = api.generate_anything_from_source(adv.new, tardir, mkdtemp(prefix='size_new_', dir=tmpdir), analytics.file_size_callback)
        sizes_new = analytics.normalize_list_of_dict_into_dict(sizes_new)

        # Pull code from upstream
        # NB: After this function PWD will be changed
        utils.checkout_or_pull(dirname, adv.old.package.scmurl, SCM_CLONE_CMD[pkg_scm_type], SCM_PULL_CMD[pkg_scm_type])


        # tag names match pv.version
        api_version_old = adv.old.version.replace(" ", "_")
        api_version_new = adv.new.version.replace(" ", "_")

        if pkg_scm_type in [utils.SCM_TARBALL]:
            # tarball dir tags versions the same way api dir does
            version_old = api_version_old
            version_new = api_version_new

        # if changelog is specified and exists use it. otherwise try to find it
        if changelog_file and (changelog_file != 'None'): # os.path.exists(dirname + '/' + changelog_file):
            pass
        elif changelog_file == 'None':
            changelog_file = None
        elif pkg_scm_type != utils.SCM_METACPAN: # metacpan doesn't checkout source so find always fails
            search_dir = dirname
            if adv.old.package.subpackage_path:
                search_dir = os.path.join(search_dir, adv.old.package.subpackage_path)
            changelog_file = utils.which_changelog(utils.files_in_dir(search_dir))

        # First compile the changelog text from diff for the Changelog file
        if changelog_file and SCM_DIFF_CHANGELOG_CMD[pkg_scm_type]:
            cmdline = SCM_DIFF_CHANGELOG_CMD[pkg_scm_type] % (version_old, version_new, changelog_file)
            proc = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=dirname)

            news = proc.communicate()[0]
            news = _compress_data_if_needed(news, adv.get_path(), 'changelog')
            # decode after save to S3 and truncate
            news = news.decode('UTF8', 'replace')
        else: # No changelog
            news = utils.INFO_NOT_AVAILABLE

        # in case changelog returns empty string
        if not news:
            news = utils.INFO_NOT_AVAILABLE

        # calculate change rate based on total size changes.
        if adv.old.size is None:
            old_size = utils.get_size(adv.old.download_url)
            adv.old.size = old_size # temp assign, b/c not .save()'d
            PackageVersion.objects.filter(pk=adv.old_id).update(size=old_size)

        if adv.new.size is None:
            new_size = utils.get_size(adv.new.download_url)
            adv.new.size = new_size # temp assign, b/c not .save()'d
            PackageVersion.objects.filter(pk=adv.new_id).update(size=new_size)

        change_rate = utils.change_rate(adv.new.size, adv.old.size)
        severity = utils.which_severity(change_rate)
        adv.severity = severity # temp assign, b/c not .save()'d

        # store changelog into S3
        file_path = _create_json_file(adv.pk, adv.get_path(), 'changelog', news)

        # save the changelog
        Advisory.objects.filter(
                pk=adv.pk
            ).update(
                # set change rate % and severity
                type = change_rate,
                severity = severity,
                # mark if we're using git or tarball
                overriden = override
            )

        cmdline = None
        if adv.old.package.subpackage_path and SCM_LOG_PATH_CMD[pkg_scm_type]:
            cmdline = SCM_LOG_PATH_CMD[pkg_scm_type] % (version_old, version_new, adv.old.package.subpackage_path)
        elif SCM_LOG_CMD[pkg_scm_type]:
            cmdline = SCM_LOG_CMD[pkg_scm_type] % (version_old, version_new)

        if cmdline is not None:
            changelog = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=dirname).communicate()[0]
            changelog = _compress_data_if_needed(changelog, adv.get_path(), 'commit_log')
            # decode after save to S3 and truncate
            changelog = changelog.decode('UTF8', 'replace')
        else:
            changelog = utils.INFO_NOT_AVAILABLE

        # store commit log into S3
        file_path = _create_json_file(adv.pk, adv.get_path(), 'commit_log', changelog)

#### MORE tests - analytics
        try:
            more = { 'tests' : [] }

            ### API diff test
            skip_api_url = False
            # avoid "100% compatibility" message for unsupported languages where API is missing
            if api_was_generated:
                (severity, api_diff) = analytics.api_diff(apidir, api_version_old, api_version_new)
            else:
                api_diff = utils.INFO_NOT_AVAILABLE
                skip_api_url = True

            # store api_diff into S3
            api_diff_path = _create_json_file(adv.pk, adv.get_path(), 'api_diff', api_diff)

            ### API diff stats test
            if api_diff == utils.INFO_NO_API_DIFF_FOUND:
                text = utils.INFO_NO_API_DIFF_FOUND
                skip_api_url = True
            else:
                (severity, text) = analytics.diff_stats(utils.SCM_APIGEN, apidir, api_version_old, api_version_new, True, adv.old.package.subpackage_path)

            test_name = "API diff"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }
            if not skip_api_url:
                more[test_name]['u'] = api_diff_path

            ### FULL DIFF
            (severity, diff) = analytics.full_diff(pkg_scm_type, dirname, version_old, version_new, adv.old.package.subpackage_path)
            diff = _compress_data_if_needed(diff, adv.get_path(), 'diff')
            # store full_diff into S3
            diff = diff.decode('UTF8', 'replace') # decode after bzipping b/c compress fails otherwise
            full_diff_path = _create_json_file(adv.pk, adv.get_path(), 'full_diff', diff)

            ### FULL DIFF stats test
            (severity, text) = analytics.diff_stats(pkg_scm_type, dirname, version_old, version_new, True, adv.old.package.subpackage_path)
            test_name = "Full diff"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,  # 3 files changed, etc.
                'u' : full_diff_path,
            }


            ### Package size change
            (severity, text) = analytics.package_size_change(adv)
            test_name = "Package Size Change"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }

            ### File size changes
            (severity, text) = analytics.file_size_changes(sizes_old, sizes_new)
            test_name = "File Size Change"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }

### TODO: remove API diff and Full diff from the public template when launching subscriptions

            ### FILE LIST TESTS

            ### Added non-text files
            (severity, text) = analytics.added_non_text_files(old_filetypes, new_filetypes)
            test_name = "Added non-text Files"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }


            ### Modified files test
            # NB: tarball dir tags versions the same way api dir does
            (severity, text) = analytics.list_modified_files(tardir, api_version_old, api_version_new)
            test_name = "Modified Files"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }

            ### File list changes
            (severity, file_list) = analytics.get_file_list_changes(tardir, api_version_old, api_version_new)

            ### Added files
            (severity, text) = analytics.filter_added_files(file_list)
            test_name = "Added Files"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }


            ### Removed files
            (severity, text) = analytics.filter_removed_files(file_list)
            test_name = "Removed Files"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }

            ### Renamed files
            (severity, text) = analytics.filter_renamed_files(file_list)
            test_name = "Renamed Files"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }

            ### File permissions change
            (severity, text) = analytics.filter_permission_change(file_list)
            test_name = "Permissions Change"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }


            ### Symlinks 
            (severity, text) = analytics.symlinks_test(tardir) # NB: tardir has cheched out the NEW version
            test_name = "Symlinks"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }

            ### File types change test
            (severity, text) = analytics.file_types_diff(magicdir, api_version_old, api_version_new)
            test_name = "File Types Change"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }


            ### Virus scan
            (severity, text) = analytics.virus_scan(tardir)
            (severity, text) = analytics.parse_virus_scan(text) # returns all text w/ Infected files: X at the top

            test_name = "Virus Scan"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }


            ### Test case count
            (severity, text) = analytics.test_case_count_change(old_tests, new_tests)
            test_name = "Test Cases"
            more['tests'].append(test_name)
            more[test_name] = {
                's' : severity,
                't' : text,
            }


            _create_json_file(adv.pk, adv.get_path(), 'more', more, False) # don't escape
        except:
#            raise
            exception_text = "Exception: %s\n" % sys.exc_info()[1]
            exception_text += "\n".join(format_tb(sys.exc_info()[2]))
            _create_json_file(adv.pk, adv.get_path(), 'more', exception_text)

### BUGS
        find_bugs(adv.id, news, changelog) # this will change status to MODIFIED

        logger.info("Generated diff files for %s" % adv.__unicode__())
    finally:
        # always remove the API dir b/c once generated (even empty files) there's no way
        # we can tell that on subsequent runs. This means showing NO API DIFF for packages
        # where API diff is not supported. The API will be regenerated on the next run
        shutil.rmtree(apidir, True)
        shutil.rmtree(magicdir, True)

    reset_queries()

@task
def find_bugs(id, changelog = None, commit_log = None):
    """
        Find bugs.

        @id - Advisory.pk
        @changelog - string - the changelog text
        @commit_log - string - the commit log text
    """

    logger = find_bugs.get_logger()
    logger.info('Will search for bugs')

    try:
        # fetch other fields as needed
        adv = Advisory.objects.filter(pk=id).only('id', 'status')[0]
    except IndexError:
        reset_queries()
        return

    if (adv.status >= STATUS_PUSH_READY):
        return

    # delete previously found bugs and search again
    utils.get_bugs_query(id).delete()

    try:
        removed_lines = ""
        added_lines = ""

        if changelog:
            search_in = changelog
#TODO: fetch changelog data from JSON
#        else:
#            pass

        if commit_log:
            added_lines = commit_log
#TODO: fetch changelog data from JSON
#        else:
#            pass

        # inspect only newly added lines to minimize errors
        for line in search_in.split("\n"):
            if line.startswith('+'):
                added_lines += "\n" + line
            elif line.startswith('-'):
                removed_lines += "\n" + line

        regexp = bugs.get_bug_regexp()
        bug_dict = regexp.findall(added_lines)
        bug_dict = bugs.extract_bug_numbers(bug_dict)
        # NB: ^^^ now bug_dict is a dict - { num : context }
        bug_nums = bug_dict.keys()
        bug_nums.sort()

        # filter bug numbers which are also present on deleted lines.
        # common case is when leading/trailing spaces are updated
        for bug in bug_nums:
            if removed_lines.find("%d" % bug) > -1:
                # NB: remove from both data structures
                bug_nums.remove(bug)
                del bug_dict[bug]


        bug_format_str = adv.old.package.bugurl or 'http://example.com/%d'

        for b in bug_nums:
            try:
                url = bug_format_str % b
# TODO: skip fetch_page if in DB
                page = utils.fetch_page(url)
                (title, reported_on, closed_on) = bugs.extract_title_and_dates_from_html(page, adv.old.package.bugtype)
                Bug.objects.get_or_create(advisory=adv, number=b, url=url, title=title, context=bug_dict[b], reported_on=reported_on, closed_on=closed_on)
            except:
                logger.error("Failed to get info for bug %d: %s" % (b, sys.exc_info()[1]))
                logger.error(format_tb(sys.exc_info()[2]))
                Bug.objects.get_or_create(advisory=adv, number=b, url=url, title="FAILED: %s" % sys.exc_info()[1], context=bug_dict[b])
                continue

        Advisory.objects.filter(
                pk=adv.pk
            ).update(
                status = STATUS_MODIFIED,
                last_updated = datetime.now()
            )

        logger.info("Found bugs for %s" % adv.__unicode__())
    except:
        logger.error("Exception: %s" % sys.exc_info()[1])
        logger.error(format_tb(sys.exc_info()[2]))

    reset_queries()

@task
def cron_move_advisories_to_live():
    """
        Move advisories to LIVE, send notifications, etc.
        Executed by CRON.
    """
    logger = cron_move_advisories_to_live.get_logger()

    logger.info("Moving advisories to LIVE")

    query = Advisory.objects.filter(status=STATUS_PUSH_READY)

    for adv in query:
        # go through all apps which currently have this package installed
        # and update them.
#todo: if 1 app has 2 updates released together this will update status and cache twice
        for inst in InstalledPackage.objects.filter(application__gt=0, version=adv.old_id).only('application'):
            update_application_status.delay(inst.application, APP_STATUS_NEEDSUPDATE)

    # move to LIVE
    affected = query.update(status=STATUS_LIVE)

    if affected > 0:
        generate_static_pages.delay()

    reset_queries()

@task
def cron_update_application_status():
    """
        Set application status to NEEDSUPDATE or UPTODATE.
        Executed by CRON.
    """
    logger = cron_update_application_status.get_logger()
    logger.info("Changing application statuses")

    # only select apps that are APPROVED, UPTODATE or NEEDSUPDATE
    query = Application.objects.filter(status__in=[APP_STATUS_APPROVED, APP_STATUS_UPTODATE, APP_STATUS_NEEDSUPDATE])

    for app in query:
        update_application_status.delay(app.id)

    reset_queries()


@task
def update_application_status(id, status=None):
    """
        Set application status to NEEDSUPDATE or UPTODATE.
        Not executed by CRON.

        @id - integer - Application object id
    """
    logger = update_application_status.get_logger()
    logger.info("Changing application status")

    try:
        app = Application.objects.filter(pk=id).only('id', 'status', 'name')[0]
    except IndexError:
        return

    # if removed in the mean time
    if app.status <= APP_STATUS_PENDING:
        return

    status_is_updated = False

    # if status is specified then set it and exit
    if status:
        if app.status != status:
            Application.objects.filter(pk=app.pk).update(status=status)
            status_is_updated = True
    else:
        for inst in InstalledPackage.objects.filter(application=app.pk).only('version'):
            # count how many advisories we have for this installed package
            adv_count = Advisory.objects.filter(old=inst.version, status=STATUS_LIVE).count()

            if adv_count > 0:
                logger.info("Application %s (%d) NEEDSUPDATE" % (app.name, app.id))

                if app.status != APP_STATUS_NEEDSUPDATE:
                    Application.objects.filter(pk=app.pk).update(status=APP_STATUS_NEEDSUPDATE)

                # no matter if we hit DB mark as updated to avoid setting to UPTODATE below
                status_is_updated = True

                # no need to count anymore for this app
                break

        # if no advisories found then the application is up-to-date
        if (not status_is_updated) and (app.status != APP_STATUS_UPTODATE):
            logger.info("Application %s (%d) is UPTODATE" % (app, app.id))

            Application.objects.filter(pk=app.pk).update(status=APP_STATUS_UPTODATE)
            status_is_updated = True

    reset_queries()


def _create_json_file(adv_pk, adv_path, field, content, do_escape=True):
    """
        Generate JSON files and store them in S3

        @adv_pk - string/ID
        @adv_path - string
        @field - string - the field name
        @content - string - the content to store. if empty fetch from DB
        @private - bool - if True will save to private storage instead of public

        @return - string - the file path which was created
    """

    if not content:
        content = utils.INFO_NOT_AVAILABLE

    if do_escape:
        content = escape(content)
    content = json.dumps(content)

    file_path = adv_path + '%s.json' % field
    _create_file(file_path, content) # NB: NO MINIFY !!!

    return file_path


def _create_file(filename, contents):
    """
        Helper function.
    """
    # save to S3
    default_storage.save(filename, ContentFile(contents))

@task
def generate_static_pages(ignore_present = True):
    """
        Crawl some of the views and dump static HTML/CSS
        into S3.

        @ignore_present - if True will generate pages only for
        Advisory.has_static_page == False. Used for speedups.

        Call this function with False, to regenerate all pages,
        e.g. if the templates have been updated.
    """

    logger = generate_static_pages.get_logger()
    logger.info("Generating static pages")

    # for S3 storage
    HTML_ROOT = ''

    # dummy object to pass to views
    env = {
            'REQUEST_METHOD' : 'GET',
            'wsgi.input' : None,
        }
    request = WSGIRequest(env)
    request.user = AnonymousUser()

    # generate static pages for all advisories
    query = Advisory.objects.filter(status=STATUS_LIVE).only('id')

    # do not generate previously generated pages
    if ignore_present:
        query = query.filter(has_static_page=False)

    query = query.order_by('-new__released_on')

    count = 0
    top_id = 0
    for adv in query:
        adv_path = adv.get_path()
# SINCE 2013-10-19 & Advisory.pk > 23088
# analytics are not statically generated in S3
# only their JSON files are. This is to avoid changes in template/behavior
# messing up with older analytics.
#        request.path = adv_path
#        response = views.advisory(request, adv.old, adv.new, adv.id)
##        _create_file(HTML_ROOT + request.path + 'index.html', html_minify(response.content))
#        _create_file(HTML_ROOT + request.path + 'index.html', response.content) # latest htmlmin is worse than older

        count += 1
        if adv.id > top_id:
            top_id = adv.id

        # generate json content in S3
        _create_json_file(adv.pk, adv_path, 'bugs', utils.get_bugs_as_html(adv.pk), do_escape=False)

        # NB: one-by-one update is less effective but avoids race conditions where other Advisories
        # have been pushed LIVE but not have been processed yet due to slow working queues
        Advisory.objects.filter(pk=adv.pk).update(has_static_page=True)

        print "DEBUG: ", count, adv, adv.id

    # generate global RSS
    if ignore_present and (count > 0):
        # take the current objects + 50 more
        # filter by ID > XXX because slicing the query is less efficient
        query = Advisory.objects.filter(status=STATUS_LIVE, id__gte=top_id-count-50).only('id').order_by('-new__released_on')
        request.path = '/rss.xml'
        response = render(request, 'rss.xml', {'context' : query})
        _create_file(HTML_ROOT + '/rss.xml', response.content)


    # generate pages which don't have arguments
    # at the end to avoid some 404s
    VIEWS = {
                urls.URL_INDEX : views.index,
                urls.URL_SEARCH : views.search_results,
                urls.URL_ANALYTICS : views.analytics,
            }

    for key in VIEWS:
        request.path = '/%s/' % key
        response = VIEWS[key](request)
#        _create_file(HTML_ROOT + key + '/index.html', html_minify(response.content))
        _create_file(HTML_ROOT + key + '/index.html', response.content) # latest htmlmin is worse than older versions


    reset_queries()


@task
def cron_delete_pending_apps(app_pk = None, user_pk = None):
    """
        Delete pending apps and their packages from DB
        if they are older than 1hr.

        @app_pk - int - if specified delete this app, instead of PENDING
        @user_pk - int - used for ownership check if app_pk is specified
    """

    if app_pk is not None:
        query = Application.objects.filter(pk=app_pk, owner=user_pk).only('pk')
    else:
        last_time = datetime.now()-timedelta(hours=1)
        query = Application.objects.filter(
                        last_checkin__lt=last_time,
                        status__lte=APP_STATUS_PENDING
                    ).only('pk')

    # get all PKs
    app_pks = set(app.pk for app in query)

    if app_pks:    # bulk delete all related objects
        ApplicationHistory.objects.filter(application__in=app_pks).delete()
        InstalledPackage.objects.filter(application__in=app_pks).delete()
        Application.objects.filter(pk__in=app_pks).delete()

    reset_queries()


@task
def cron_search_dates(id = None):
    """
        Search for release dates and update the objects.

        @id - PackageVersion id
    """

    query = PackageVersion.objects
    if not id:
        query = query.filter(released_on__isnull=True)
        # only installed PVs
        query = query.filter(pk__in=set(inst.version for inst in InstalledPackage.objects.only('version').distinct()))
    else:
        query = query.filter(pk=id)

    for pv in query.only('package'):
        pkg = Package.objects.filter(pk=pv.package_id).only('type')[0]
        pv_find_date.delay(pv.pk, PACKAGE_CALLBACKS[pkg.type]['find_date'])

    reset_queries()


@task
def pv_find_date(id, find_date_func):
    """
        Fetch the date for individual PackageVersion and save to DB.
    """

    logger = pv_find_date.get_logger()

    try:
        pv = PackageVersion.objects.filter(id=id).only('id', 'status', 'released_on', 'version')[0]
    except IndexError:
        reset_queries()
        return

    if pv.status >= STATUS_VERIFIED:
        return

    if pv.released_on and (pv.released_on != datetime(2001, 01, 01)):
        return

    logger.info('Will search release date for %s' % pv)

    try:
        released_on = find_date_func(pv.package.name, pv.version)

        if (released_on is None) and (pv.version.find(' ') > -1):
            # try finding the date based on a github commit which follows after the space
            commit = pv.version.split(' ')[1]
            if pv.package.scmurl.find('github.com') > -1:
                user_repo = github._get_user_repo(pv.package.scmurl)
                released_on = github.get_release_date_from_commit(user_repo, commit)

        if released_on:
            # don't overwrite ASSIGNED
            if pv.status == STATUS_ASSIGNED:
                status = STATUS_ASSIGNED
            else:
                status = STATUS_MODIFIED

            PackageVersion.objects.filter(id=id).update(released_on=released_on, status=status)
            logger.info('Found release date for %s' % pv)
            move_package_version_to_verified(pv.id)
    except:
        logger.error("Exception: %s" % sys.exc_info()[1])
        logger.error(format_tb(sys.exc_info()[2]))

    reset_queries()


@task
def cron_find_download_url(id = None):
    """
        Search for download URLs

        @id - PackageVersion id
    """

    query = PackageVersion.objects
    if not id:
        query = query.filter(download_url__isnull=True)
        # only installed PVs
        query = query.filter(pk__in=set(inst.version for inst in InstalledPackage.objects.only('version').distinct()))
    else:
        query = query.filter(pk=id)

    for pv in query.only('package'):
        pkg = Package.objects.filter(pk=pv.package_id).only('type')[0]
        pv_find_download_url.delay(pv.pk, PACKAGE_CALLBACKS[pkg.type]['get_download_url'])

    reset_queries()

@task
def pv_find_download_url(id, find_url_func):
    """
        Fetch the download URL for individual PackageVersion and save to DB.
    """

    logger = pv_find_download_url.get_logger()

    try:
        pv = PackageVersion.objects.filter(id=id).only('id', 'status', 'download_url', 'version')[0]
    except IndexError:
        reset_queries()
        return

    if pv.status >= STATUS_VERIFIED:
        return

    if pv.download_url:
        return

    logger.info('Will search download URLs for %s' % pv)

    try:
        download_url = find_url_func(pv.package.name, pv.version)

        # try some heuristics to fetch a tarball from GitHub
        # if no URL found or there's a space in the version (commit hash follows)
        if (not download_url) or (pv.version.find(' ') > -1):
            if (pv.package.website.find('//github.com') > -1) and pv.scmid:
                pkg_spec = github._get_user_repo(pv.package.website)
                download_url = github.get_download_url_from_commit(pkg_spec ,pv.scmid)
            elif (pv.package.website.find('//bitbucket.org') > -1) and pv.scmid:
                download_url = "%s/get/%s.tar.bz2" % (pv.package.website, pv.scmid)

        if download_url:
            # don't overwrite ASSIGNED
            if pv.status == STATUS_ASSIGNED:
                status = STATUS_ASSIGNED
            else:
                status = STATUS_MODIFIED

            PackageVersion.objects.filter(id=id).update(download_url=download_url, status=status)
            logger.info('Found download URL for %s' % pv)
            move_package_version_to_verified(pv.pk)
    except:
        logger.error("Exception: %s" % sys.exc_info()[1])
        logger.error(format_tb(sys.exc_info()[2]))

    reset_queries()


@task
def cron_find_tags(id = None):
    """
        Search for tags.

        @id - PackageVersion id
    """

    query = PackageVersion.objects
    if not id:
        # filter only PVs for which the Package has a known SCM type b/c find tag will fail anyway
        # search where field is None, "" or "TAG-NOT-FOUND"
        query = query.filter(Q(scmid__isnull=True) | Q(scmid="") | Q(scmid=utils.TAG_NOT_FOUND), package__scmtype__gt=utils.SCM_UNKNOWN)
        # only installed PVs
        query = query.filter(pk__in=set(inst.version for inst in InstalledPackage.objects.only('version').distinct()))
    else:
        query = query.filter(id=id)

    for pv in query.only('pk'):
        pv_find_tags.delay(pv.pk)

    reset_queries()


@task
def pv_find_tags(id, search_others=False):
    """
        Fetch tags for individual PackageVersion and save to DB
        if they match with the version field.
    """

    logger = pv_find_tags.get_logger()

    try:
        pv = PackageVersion.objects.filter(id=id).only('id', 'status', 'scmid', 'version')[0]
    except IndexError:
        reset_queries()
        return

    if (pv.status >= STATUS_VERIFIED) or (pv.scmid and pv.scmid != utils.TAG_NOT_FOUND):
        return

    if (not pv.package.website) and (not pv.package.scmurl):
        return

    logger.info('Will search tags for %s-%s' % (pv.package.name, pv.version))

    try:
        tags = None
        vtag = "" # silence DB if no tags found
        pkg_scm_type = pv.package.scmtype

        # traditional SCM types
        if pv.package.website:
            if pv.package.website.find('github.com') > -1:
                tags = github.get_tags(pv.package.website)
            elif pv.package.website.find('bitbucket.org') > -1:
                tags = bitbucket.get_tags(pv.package.website)

        if (not tags) and pv.package.scmurl:
            if pv.package.scmurl.find('github.com') > -1:
                tags = github.get_tags(pv.package.scmurl)
            elif pv.package.scmurl.find('bitbucket.org') > -1:
                tags = bitbucket.get_tags(pv.package.scmurl)


        if (not tags) and SCM_LIST_TAGS_CMD[pkg_scm_type]: # Generic Git/Mercurial/Bzr
            dirname = utils.which_checkout_dir(SCM_SHORT_NAMES[pkg_scm_type], pv.package.type, pv.package.name)

            # NB: After this function PWD will be changed
            utils.checkout_or_pull(dirname, pv.package.scmurl, SCM_CLONE_CMD[pkg_scm_type], SCM_PULL_CMD[pkg_scm_type])

            cmdline = SCM_LIST_TAGS_CMD[pkg_scm_type]
            proc = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=dirname)
            tags = proc.communicate()[0].split("\n")

            if pkg_scm_type in [utils.SCM_MERCURIAL, utils.SCM_BAZAAR]:
                # cut the first column
                new_tags = []
                for t in tags:
                    new_tags.append(t.split(' ')[0])
                tags = new_tags

        # other SCMs
        if (not tags) and (pv.package.scmtype == utils.SCM_METACPAN):
            vtag = metacpan.get_tags(pv.package.name, pv.version)

        pkg_name = pv.package.name
        if pv.package.type == JAVA_MAVEN_PKG:
            [gid, pkg_name] = mavencentral._groupid_artifactid(pkg_name)
        elif pv.package.type == PYPI_PYTHON_PKG:
            pkg_name = pypi._other_name(pkg_name)
        elif pv.package.type == PERL_CPAN_PKG:
            pkg_name = cpan._other_name(pkg_name)


        if tags:
            vtag = utils.which_tag(pv.version, tags, pkg_name)

        # try using the commit hash which follows after the space
        if (vtag in ["", utils.TAG_NOT_FOUND]) and (pv.version.find(' ') > -1):
            commit = pv.version.split(' ')[1]
            if pv.package.scmurl.find('github.com') > -1:
                vtag = commit

        # try to guess the commit sha by examining the changes
        # NB: don't update vtag to prevent skipping manual inspection
        if (vtag in ["", utils.TAG_NOT_FOUND]) and (pv.released_on):
            if (pv.package.scmurl.find('github.com') > -1):
                candidates = [] # possible sha values where version changed

                user_repo = github._get_user_repo(pv.package.scmurl)
                commits = github.get_commits_around_date(user_repo, pv.released_on)

                for commit_sha in commits.keys():      # for every commit
                    for patch in commits[commit_sha]:  # inspect all patches
                        for line in patch.split('\n'): # and scan all lines
                            if line.startswith('+') and \
                                (line.lower().find('version') > -1) and \
                                (line.find(pv.version) > -1):
                                candidates.append(commit_sha)

                # avoid automatic move to VERIFIED
                if len(candidates) == 1:
                    vtag = None
                    PackageVersion.objects.filter(id=pv.id).update(scmid=candidates[0], status=STATUS_ASSIGNED)
                else:
                    print "DEBUG: find tags", candidates

        if vtag:
            # don't overwrite ASSIGNED
            if pv.status == STATUS_ASSIGNED:
                status = STATUS_ASSIGNED
            else:
                status = STATUS_MODIFIED

            PackageVersion.objects.filter(id=pv.id).update(scmid=vtag, status=status)

            logger.info('Updated tags for %s' % pv)
            move_package_version_to_verified(pv.id)

            if search_others: # if we've found any tag then try searching for the other PVs too
                for other_pv in PackageVersion.objects.filter(
                                                package=pv.package
                                            ).exclude(
                                                id=pv.id
                                            ).filter(
                                                Q(scmid__isnull=True) | Q(scmid="") | Q(scmid=utils.TAG_NOT_FOUND)
                                            ).only('id'):
                    pv_find_tags(other_pv.id, False) # avoid recursion

            # if we've found a tag and there is a LIVE advisory with this PV then
            # do nothing!!! LIVE analytics are not supposed to be updated unless requested
    except:
        logger.error("Exception for PV(%s): %s" % (id, sys.exc_info()[1]))
        logger.error(format_tb(sys.exc_info()[2]))

    reset_queries()


@task
def cron_move_package_version_to_verified():
    """
        Periodically try to move PackageVersion objects to VERIFIED.
    """
    logger = cron_move_package_version_to_verified.get_logger()
    logger.info("Trying to VERIFY PackageVersions")

    query = PackageVersion.objects.filter(
                status__lt=STATUS_VERIFIED,
                scmid__isnull=False
            ).exclude(
                scmid=""
            ).exclude(
                scmid=utils.TAG_NOT_FOUND
            )
    # only installed PVs
    query = query.filter(pk__in=set(inst.version for inst in InstalledPackage.objects.only('version').distinct()))

    for pv in query.only('pk'):
        move_package_version_to_verified.delay(pv.pk)

    reset_queries()


@task
def move_package_version_to_verified(id):
    """
        Try and move the PackageVersion object to VERIFIED.

        @id - PackageVersion ID
    """
    logger = move_package_version_to_verified.get_logger()

    try:
        # test_if_package_version_verified will access all fields
        obj = PackageVersion.objects.filter(id=id)[0]
    except IndexError:
        reset_queries()
        return

    if (obj.status >= STATUS_VERIFIED):
        return

    result = utils.test_if_package_version_verified(obj)
    status = utils.get_status(result['scores'], utils.SCORES_PACKAGE_VERSION_VERIFIED, STATUS_VERIFIED, obj.status)

    if status == STATUS_VERIFIED:
        PackageVersion.objects.filter(id=id).update(status=status)
        logger.info("Moved PackageVersion %s to VERIFIED" % obj)

    reset_queries()


@task
def helper_search_new_data(app_id):
    """
        Launch several commonly used tasks.
    """
    # if app is specified -> search new versions
    # and update status
    if app_id:
        # search new versions. Will also gater missing
        # information for old/new PackageVersions
        cron_find_new_versions.apply_async(args=[None, app_id, True], countdown=30)
        update_application_status(app_id) # NB: no delay

@task
def cron_helper_notify_app_owners(delay=1):
    """
        Notify app owners with digest.

        @delay - int - how many days back to search for updates.
    """

    end_date = datetime.now()
    start_date = datetime.now() - timedelta(days=delay)

    for user in User.objects.filter(is_active=True).only('pk'):
        # to avoid importing the UserProfile class
        # which may be defined in a private app
        profile = user.get_profile()
        if profile.get_email_delay() == delay:
            notify_app_owner_about_update.delay(user.pk, start_date, end_date, delay)

@task
@execute_once_in(3600*24*6)  # once every 6 days
def cron_notify_app_owners_7():
    """
        Notify app owners with weekly digest
    """
    cron_helper_notify_app_owners(7)

@task
@execute_once_in(3600*20)  # once every 20 hours
def cron_notify_app_owners_1():
    """
        Notify app owners with daily digest
    """
    cron_helper_notify_app_owners(1)


@task
def notify_app_owner_about_update(user_id, start_date, end_date, frequency):
    """
        Notify application owner about pending updates,
        published between @start_date and @end_date,
        respecting their email preferences.

        This new version tells people only about new package versions
        and in which apps are they used; then asks them to login to
        their dashboard to review the changes, to stimulate more site visits!

        @user_id - int - User.id
        @start_date - timestamp
        @end_date - timestamp
        @frequencey - int - daily, weekly, etc
    """

    logger = notify_app_owner_about_update.get_logger()

    email_data = {
        1 : {
            'subject' : "Latest package updates",
            'url_prefix' : 'daily',
        },

        7 : {
            'subject' : "Weekly package updates",
            'url_prefix' : 'weekly',
        },
    }

    try:
        user = User.objects.filter(id=user_id).only('username', 'first_name')[0]
    except IndexError:
        reset_queries()
        logger.error('No user with id %d' % user_id)
        return

    if not user.is_active:
        logger.error('User %s(%d) is not active' % (user, user_id))
        return

    if not user.email:
        logger.error('User %s(%d) does not have email' % (user, user_id))
        return

    email = user.email.strip()
    if email.find("@") == -1:
        logger.error('User %s(%d) has invalid email' % (user.username, user_id))
        return


    # store PKs, to be used later
    installed_vers = {} # installed versions and their apps
    all_apps_pks = set() # helper for easier queries later
    query = InstalledPackage.objects.filter(
                                        owner=user_id
                                    ).only(
                                        'version',
                                        'application'
                                    )
    for inst in query:
        if not installed_vers.has_key(inst.version):
            installed_vers[inst.version] = set()

        installed_vers[inst.version].add(inst.application)
        all_apps_pks.add(inst.application)


    # build a map of new versions and corresponding apps
    new_versions = {}
    query = Advisory.objects.filter(
                            old__in=installed_vers.keys(),
                            status=STATUS_LIVE,
                            last_updated__gte=start_date,
                            last_updated__lte=end_date,
                        ).only('old', 'new')

    for adv in query:
        if not new_versions.has_key(adv.new_id):
            new_versions[adv.new_id] = set() # set of affected apps

        new_versions[adv.new_id].update(installed_vers[adv.old_id])


    if len(new_versions.keys()) <= 0:
        logger.info('User %s(%d) does not have any new updates' % (user, user_id))
        return

    # fetch app names. these are by definition already approved
    app_name_map = {}
    app_name_map[0] = "Follow Packages"
    for app in Application.objects.filter(pk__in=all_apps_pks).only('name'):
        app_name_map[app.pk] = app.name

    # store Package.name and PackageVersion.version
    # keys are Object.pk
    name_map = {}
    ver_map = {}
    ver_pkg_pks = set()

    # fetch NEW versions as string
    for ver in PackageVersion.objects.filter(pk__in=new_versions.keys()).only('version', 'package'):
        ver_map[ver.pk] = { 'v' : ver.version, 'p' : ver.package_id }
        ver_pkg_pks.add(ver.package_id)

    # fetch NEW package names
    for pkg in Package.objects.filter(pk__in=ver_pkg_pks).only('name'):
        name_map[pkg.pk] = pkg.name


    released_items = {}
    # build a list of released items for the email template
    for new_pk in new_versions.keys():
        package_pk = ver_map[new_pk]['p']
        package_name = name_map[package_pk]
        new_version = ver_map[new_pk]['v']

        new_release = "%s-%s" % (package_name, new_version) # e.g. Django-1.5.2
        # figure out which apps use this package
        apps = []
        for app in new_versions[new_pk]:
            apps.append(app_name_map[app])
        apps.sort()

#        print new_release, apps

        released_items[new_release] = apps

    nvrs = released_items.keys()
    nvrs.sort()

    sorted_released_items = []
    for nvr in nvrs:
        sorted_released_items.append(
                                    {
                                        'nvr' : nvr,
                                        # work around comma issue in templates
                                        'apps' : ', '.join(released_items[nvr]), 
                                    }
                                )

    try:
        send_templated_mail(
            template_name='update_digest',
            from_email="Difio <%s>" % settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            context={
                'email_subject' : email_data[frequency]['subject'],
                'username': user.username,
                'full_name': user.first_name,
                'start_date' : start_date,
                'end_date' : end_date,
                'released_items' : sorted_released_items,
            },
        )
    except:
        pass

    logger.info("Sent notification to %s" % user)
    reset_queries()

@task
def generate_application_history_records(app_id, when = None):
    """
        After application/package list has been updated store the current state in the DB.

        @app_id - Application.id
        @when - datetime - optional

TODO: fix slow queries!!!
TODO: when importing refactor to just save the text of the import (from URL, upload, etc)
    """

    text = ""
    name_ver = {}
    for installed in InstalledPackage.objects.filter(application=app_id).only('package', 'version'):
        try:
            package = Package.objects.filter(pk=installed.package).only('name')[0]
            version = PackageVersion.objects.filter(pk=installed.version).only('version')[0]
            name_ver['%s-%s' % (package.name, version.version)] = 1
        except:
            continue

    # sort by name
    names = name_ver.keys()
    names.sort()
    for n in names:
        text += "%s\n" % n

    if when is None:
        when = datetime.now()

    ApplicationHistory.objects.create(application_id=app_id, when_added=when, packages=text)



@task
def do_stuff_when_packages_change(app_id):
    """
        This task is executed always when packages have been changed

        @app_id - int - Application identifier
    """

#todo: this method utilizes slow queries - fix it

    # save the current state into the DB
    generate_application_history_records(app_id)


@task
def import_application(app_pk, app_uuid, owner_pk, is_manual_import, is_first_import):
    """
        Executed from views.application_register to import packages/versions
        in the backend. This is to speedup the UI and offload the AppServer.

        @app_pk - int - the application ID
        @app_uuid - string - the application UUID
        @owner_pk - int - the application owner ID
        @is_manual_import - bool - if importing manually
        @is_first_import = boot - True if importing for the first time.
    """
    # using cache to pass the data parameter to avoid
    # reaching SQS message size limit
    task_cache = cache_module.get_cache('taskq')
    data = task_cache.get(app_uuid)

    # expired or error.
    # anyway this error condition is beyond repair
    # cron will delete the NEW app in the next hour
#    if data is None:
#        return
    # allow it to raise so we receive notifications

    # list of latest installed packages. Used for bulk-delete later
    latest_installed = []
    new_package = False

    # add packages and versions, already sanitized
    for n_v_r in data['installed']:

        if n_v_r.has_key('t'):
            pkg_type = n_v_r['t']
        else:
            pkg_type = data['pkg_type']

        try:
            package = Package.objects.filter(name=n_v_r['n'], type=pkg_type)[0]
        except IndexError:
            package = Package.objects.create(name=n_v_r['n'], type=pkg_type)
            new_package = True

        try:
            version = PackageVersion.objects.filter(package=package.pk, version=n_v_r['v'])[0]
        except IndexError:
            version = PackageVersion.objects.create(package=package, version=n_v_r['v'])
            new_package = True

        try:
            installed = InstalledPackage.objects.filter(version=version.pk, application=app_pk)[0]
        except IndexError:
            installed = InstalledPackage.objects.create(application=app_pk, owner=owner_pk, version=version.pk, package=package.pk)
            new_package = True

        latest_installed.append(installed.id) 


    # delete packages that are no longer present
    # NB: this needs to be executed last to preserve prior state on errors
    # in case of errors, just re-push
    query = InstalledPackage.objects.filter(application=app_pk).exclude(pk__in=latest_installed)
    if query.count() > 0: # packages have changed
        query.delete()
        new_package = True

    search_data = True
    if is_first_import:
        # automated import
        search_data = False
        status_tobe = APP_STATUS_PENDING

        # if first-time manual import always set to Approved
        if is_manual_import:
            status_tobe = APP_STATUS_APPROVED
            search_data = True
#NB: in case of refreshing existing app status is not set to IMPORTING and thenback to its value
        # all import/delete done. set proper app status
        Application.objects.filter(pk=app_pk).update(status=status_tobe)
    else: # existing application
        if data['name_url_type_changed']: # these can change, although rarely
            Application.objects.filter(
                        pk=app_pk
                    ).update(
                        name = data['app_name'],
                        type = data['app_type'],
                        url = data['app_url'],
                        last_checkin = datetime.now()
                    )
        else: # update only last_checkin time
            Application.objects.filter(
                        pk=app_pk
                    ).update(
                        last_checkin = datetime.now()
                    )

    if new_package:
        do_stuff_when_packages_change.delay(app_pk)

    # schedule action only for approved apps to avoid double scheduling on register+approve
    if search_data:
        helper_search_new_data.delay(app_pk)

