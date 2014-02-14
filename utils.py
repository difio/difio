# -*- coding: utf8 -*-

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
import tar
import json
import shutil
import urllib
import httplib
import logging
import tempfile
from bugs import BUG_TYPE_UNKNOWN
from xml.dom.minidom import parse
from htmlmin.minify import html_minify
from BeautifulSoup import BeautifulSoup
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

URL_ADVISORIES = 'updates'

VIEW_PAGINATOR = 100

TAG_NOT_FOUND="TAG-NOT-FOUND"
INFO_NOT_AVAILABLE="We're sorry! This information is not available."
MYSQL_MAX_PACKET_SIZE = 3*1024*1024 # 3 MB. The actual is 5 MB but we need some more room for additional messages
INFO_DATA_TOO_BIG = """
We're sorry! This data is too big to be displayed in a browser.
Below you can see a truncated part of it. If you still need everything
you can download a raw copy at %s
"""
INFO_NO_API_DIFF_FOUND="No API differences found!"

# how much scores do we need to move to VERIFIED
# defined here because used in multiple places
SCORES_PACKAGE_VERIFIED = 4

SCORES_PACKAGE_VERSION_VERIFIED = 5


SCM_UNKNOWN = -1
SCM_GIT = 0
SCM_MERCURIAL = 1
SCM_BAZAAR = 2
SCM_SUBVERSION = 3
SCM_CVS = 4
SCM_METACPAN = 5
SCM_TARBALL = 6
SCM_APIGEN = 7
SCM_MAGIC = 8

# severity constants
SEVERITY_NA = -2
SEVERITY_UNKNOWN = -1
SEVERITY_LOW = 0
SEVERITY_MEDIUM = 1
SEVERITY_HIGH = 2
SEVERITY_URGENT = 3


def fetch_page(url, decode=True, last_modified=None, extra_headers={}, method='GET', body=None):
    """
        @url - URL of resource to fetch
        @decode - if True will try to decode as UTF8
        @last_modified - datetime - if specified will try a conditional GET
        @extra_headers - dict - headers to pass to the server
        @method - string - HTTP verb
        @body - string - HTTP request body if available. Used for POST/PUT

        @return - string - the contents from this URL. If None then we probably hit 304 Not Modified
    """

    (proto, host_path) = url.split('//')
    (host_port, path) = host_path.split('/', 1)
    path = '/' + path

    if url.startswith('https'):
        conn = httplib.HTTPSConnection(host_port)
    else:
        conn = httplib.HTTPConnection(host_port)

    # some servers, notably logilab.org returns 404 if not a browser
    # GitHub also requires a valid UA string
    headers = {
        'User-Agent' : 'Mozilla/5.0 (X11; Linux x86_64; rv:10.0.5) Gecko/20120601 Firefox/10.0.5',
    }

    # workaround for https://code.google.com/p/support/issues/detail?id=660
    real_method = method
    if (method == "HEAD") and ((url.find('googlecode.com') > -1) or (url.find('search.maven.org') > -1)):
        real_method = "GET"
        headers['Range'] = 'bytes=0-9'

    # add additional headers
    for h in extra_headers.keys():
        headers[h] = extra_headers[h]

    if last_modified:
        # If-Modified-Since: Thu, 28 Jun 2012 12:02:45 GMT
        headers['If-Modified-Since'] = last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')

#    print "DEBUG fetch_page - before send", method, path, headers

    conn.request(real_method, path, body=body, headers=headers)
    response = conn.getresponse()

#    print "DEBUG fetch_page - after send", response.getheaders(), response.status

    if (response.status == 404):
        raise Exception("404 - %s not found" % url)

    if response.status in [301, 302]:
        location = response.getheader('Location')
        logger.info("URL Redirect %d from %s to %s" % (response.status, url, location))
        return fetch_page(location, decode, last_modified, extra_headers, method)

    # not modified
    if response.status == 304:
        print "DEBUG: 304 %s" % url
        return None

    if (method == "HEAD"):
        if response.status == 200:
            return response.getheader('Content-Length')
        elif response.status == 206: # partial content
            return response.getheader('Content-Range').strip().split(' ')[1].split('/')[1]


    if decode:
        return response.read().decode('UTF-8', 'replace')
    else:
        return response.read()

def get_size(url):
    """
        Get object size in bytes.
    """
    size = fetch_page(url, method="HEAD")
    return int(size)

def get_checkout_url(homepage):
    """
        Construct checkout URL if homepage is at some well
        known location like GitHub.
    """

    try:
        if homepage.find('://github.com') > -1:  # toplevel GitHub pages
            p = homepage.split('/')
            return 'git://github.com/%s/%s.git' % (p[3], p[4])
        elif homepage.find('.github.com') > -1:  # GitHub project pages
            p = homepage.split('/')
            u = p[2].split('.')[0]
            return 'git://github.com/%s/%s.git' % (u, p[3])
        elif homepage.find('://bitbucket.org') > -1:
            p = homepage.split('/')
            return "ssh://hg@bitbucket.org/%s/%s" % (p[3], p[4])
        elif homepage.find('://gitorious.org') > -1:
            p = homepage.split('/')
            return 'git://gitorious.org/%s/%s.git' % (p[3], p[4])
        else:
            return None
    except:
        logger.error("get_checkout_url for " + str(homepage))
        return None

def normalize_checkout_url(checkout):
    """
        Return URL which is ready for git clone or similar.
    """

    url = None

    if checkout.startswith('git://'):
        return checkout
    elif checkout.endswith('.git'):
        return checkout
    elif checkout.startswith('git@github.com'):  # private github url
        p = checkout.split('/')
        return "git://github.com/%s/%s/" % (p[0].split(':')[1], p[1])
    elif checkout.startswith('http'):
        # many packages (e.g.Ruby) point to the github pages instead
        # of the checkout URL directly.
        url = get_checkout_url(checkout)

    return url or checkout

def get_scm_type(checkout, old_type = None):
    """
        Return scm type for some well known providers.
    """

    if checkout is None:
        return SCM_UNKNOWN

    if checkout.startswith('git://'):
        return SCM_GIT
    elif checkout.endswith('.git'):
        return SCM_GIT
    elif checkout.find('git@') > -1:
        return SCM_GIT
    elif checkout.find('github.com') > -1:
        return SCM_GIT
    elif checkout.find('code.google.com/p/guava-libraries') > -1:
        return SCM_GIT
    elif checkout.find('code.google.com/p/pyodbc/') > -1:
        return SCM_GIT
    elif checkout.find('code.google.com/p/ruby-ole/') > -1:
        return SCM_GIT
    elif checkout.find('hg@') > -1:
        return SCM_MERCURIAL
    elif checkout.find('hg.') > -1:
        return SCM_MERCURIAL
    elif checkout.find('svn') > -1:
        return SCM_SUBVERSION
    elif checkout.find('lp:') > -1:
        return SCM_BAZAAR
    elif checkout.find('metacpan.org') > -1:
        return SCM_METACPAN
    else:
        return old_type # or SCM_UNKNOWN


def ver_date_cmp(ver1, date1, ver2, date2, ver_cmp):
    """
        Compare versions either by looking at the version string,
        or by looking at the release dates.
    """

    # if the package module provided a native compare function
    # then compare the version strings. This should be more
    # accurate and the preferred method.
    if ver_cmp:
        return ver_cmp(ver1, ver2)

    # No ver_cmp provided, e.g. Perl. fall back to
    # date comparison. Newer versions have more recent dates

    # consider date2 newer if date1 is None
    if date1 is None:
        return 1

    if date1 > date2:
        return 1

    if date1 < date2:
        return -1

    return 0

def which_tag(version, tags, name = None, reverse=False):
    """
        Match version string against tag names.

        @version - string
        @tags - list, can be None if reverse=True
        @name - package name
        @reverse - if True will consider @version to be a tag name and 
                   return version string for it
    """

    # since 2013-03-25 tags can be either dict or list (backward compatible code)
    # if dict keys are tag names, values are commit hash
    # if list make the data structure compatible
    if type(tags) is list:
        dtags = {}
        for t in tags:
            dtags[t] = t
        tags = dtags

    # format string is for regular search
    # regexp is for reverse search
    tag_formats = [
        ('%s',               '(.*)'),
        ('r%s',              'r(.*)'),
        ('r%s-1',            'r(.*)-1'), # pykickstart
        ('v%s',              'v(.*)'),
        ('v_%s',             'v_(.*)'), # https://github.com/qos-ch/slf4j/tags
        ('V%s',              'V(.*)'),
        ('v.%s',             'v\.(.*)'),
        ('V.%s',             'V\.(.*)'),
        ('v%s-tag',          'v(.*)-tag'),
        ('version-%s',       'version-(.*)'),
        ('version_%s',       'version_(.*)'),
        ('rel_%s',           'rel_(.*)'),
        ('rel-%s',           'rel-(.*)'),
        ('REL_%s',           'REL_(.*)'),
        ('REL-%s',           'REL-(.*)'),
        ('release_%s',       'release_(.*)'),
        ('release_v%s',       'release_v(.*)'),
        ('release-%s',       'release-(.*)'),
        ('release/%s',       'release/(.*)'),
        ('release/v%s',       'release/v(.*)'),
        ('RELEASE_%s',       'RELEASE_(.*)'),
        ('RELEASE-%s',       'RELEASE-(.*)'),
        ('%s-release',       '(.*)-release'),
        ('cpan-releases/%s', 'cpan-releases/(.*)'),
        ('tag/%s',           'tag/(.*)'),
        ('tag/%s-release',   'tag/(.*)-release'),
        ('tag/%s_release',   'tag/(.*)_release'),
        ('TAG_%s',           'TAG_(.*)'),
        ('PYTHON_DEFER_%s',  'PYTHON_DEFER_(.*)'),
    ]

    # PHP tags on GitHub are php-VERSION
    if (name == 'php/php-src') or (name == 'php-src'):
        name = 'php'

    # Ruby tags use the preview number as well
    if (name == 'ruby/ruby') or (name == 'ruby'):
        # ruby-1.9.3-p194 => 1.9.3.194 => v1_9_3_194
        m = re.match('([\d.]+)-p(\d+)', version)
        if m:
            version = "%s.%s" % (m.group(1), m.group(2))

    if name == 'rmagic':
        name = 'RMagic'
    elif name == 'selenium-webdriver': # Ruby
        name = 'selenium'

    if name:
        tag_formats.append((name+'-version-%s', name+'-version-(.*)')) # pylint-version-0.21.0
        tag_formats.append((name+'-v%s', name+'-v(.*)')) # twitter-v0.7.0
        tag_formats.append((name.replace('.', '')+'-%s', name.replace('.', '')+'-(.*)')) # web.py -> webpy-xyz
        tag_formats.append((name+'-%s', name+'-(.*)')) # python-ptrace-0.6.4
        tag_formats.append(('python-'+name+'-%s', 'python-'+name+'-(.*)')) # python-ecdsa-0.10, NAME is ecdsa
        tag_formats.append((name.upper()+'-%s', name.upper()+'-(.*)')) # PRAW-1.0
        tag_formats.append((name+'_%s', name+'_(.*)')) # php_5_4_0
        tag_formats.append((name+'/%s', name+'/(.*)')) # libwww-perl/5.827
        tag_formats.append((name.replace('::', '-')+'/%s', name.replace('::', '-')+'/(.*)')) # libwww-perl/5.827
        tag_formats.append((name.replace('::', '-')+'-%s', name.replace('::', '-')+'-(.*)')) # XML-LibXML-1.96
        tag_formats.append((name.upper().replace('-', '_')+'-%s', name.upper().replace('-', '_')+'-(.*)')) # py-bcrypt-0.3 => PY_BCRYPT-0_3
        tag_formats.append((name.upper().replace('-', '_')+'_%s', name.upper().replace('-', '_')+'_(.*)')) # py-bcrypt-0.3 => PY_BCRYPT_0_3


    # return version string from tag name
    if reverse:
        for (f, r) in reversed(tag_formats):
            m = re.match(r, version)
            if m:
                return m.group(1)

        return None

    # return tag name from version string
    for t in tags.keys():
        for (f, r) in tag_formats:
            if t == f % version:
                return tags[t]
            elif t.lower() == (f % version).lower(): # reportlab vs. ReportLab_0_3
                return tags[t]                     # should also match the bottom .upper()
#todo: need to make this cleaner
            elif t.lower() == (f % version.replace('.', '_')).lower(): # reportlab vs. ReportLab_0_3
                return tags[t]                     # should also match the bottom .upper()
            elif t == f % version.upper(): # 1.7.0.rc2 => 1.7.0.RC2
                return tags[t]
            elif t == f % version+'.0': # ngram 3.2 => tag 3.2.0
                return tags[t]
            elif t == f % version.replace('.', '_'):  # rel_0_7_6
                return tags[t]
            elif t == f % version.replace('.', '-'):  # RMagick_2-13-1
                return tags[t]
            elif t == f % version.replace('.', ''):  # log4perl 1.38 => rel_138
                return tags[t]

    return TAG_NOT_FOUND

def which_changelog(files):
    """
        Try to guess which file is the changelog.

        NB: Keep the list sorted for readability.
        Only filenames here, not paths.
    """

    if not files:
        return ""

    CHANGELOG_NAMES = [
        'change_log.txt',
        'changelog',
        'changelog.html',
        'Changelog',
        'Changelog.txt',
        'ChangeLog',
        'CHANGE_LOG',
        'CHANGELIST',
        'CHANGELOG',
        'ChangeLog.0',
        'ChangeLog.1',
        'CHANGELOG.markdown',
        'changelog.md',
        'changelog.mdown',
        'CHANGELOG.md',
        'Changelog.md',
        'CHANGELOG.rdoc',
        'Changelog.rdoc',
        'changelog.rst',
        'Changelog.php',
        'Changelog.rst',
        'CHANGELOG.rst',
        'changelog.txt',
        'CHANGELOG.textile',
        'CHANGELOG.txt',
        'CHANGE_LOG.txt',
        'ChangeLog.md',
        'ChangeLog.txt',
        'ChangeLog.xml',
        'ChangeLog.yaml',
        'Changes',
        'Changes.md',
        'Changes.markdown',
        'CHANGES',
        'CHANGES.md',
        'CHANGES.markdown',
        'changes.pod',
        'changes.rst',
        'CHANGES.rst',
        'CHANGES.txt',
        'CHANGES.textile',
        'Changes.textile',
        'history.txt',
        'HISTORY',
        'History',
        'HISTORY.html',
        'History.md',
        'HISTORY.md',
        'History.markdown',
        'History.rdoc',
        'HISTORY.rdoc',
        'HISTORY.rst',
        'History.txt',
        'HISTORY.txt',
        'NEWS',
        'NEWS.md',
        'news.rst',
        'News.rst',
        'NEWS.rst',
        'news.txt',
        'NEWS.txt',
        'package.xml', # for PEARs which have GitHub but no real ChangeLog
        'release-notes',
        'RELEASE_NOTES.txt',
        'RELEASE-NOTES.txt',
        'RELEASE.rdoc',
    ]

    for f in files:
        if os.path.basename(f) in CHANGELOG_NAMES:
            return f

    return ""

def get_changelog(url):
    """
        Return changelog if possible
    """

    if not url:
        return ""

    files = []

    # NB: import here because which_tag() is imported into
    # github module to avoid cirluar imports
    from github import get_files as github_get_files
    from metacpan import get_files as metacpan_get_files
    from bitbucket import get_files as bitbucket_get_files

    if url.find('github.com') > -1:
        files = github_get_files(url)
    elif url.find('bitbucket.org') > -1:
        files = bitbucket_get_files(url)
    elif url.find('metacpan.org') > -1:
        files = metacpan_get_files(url)

    return which_changelog(files)

def test_if_package_verified(obj):
    """
        Test if all required data is present and the Package
        can safely be moved to VERIFIED.

        @obj - Package object.
        @return - { 'scores' - int, 'messages' : list of (level, message) }
    """
    from django.contrib.messages import constants as message_levels

    result = {
        'scores' : 0,
        'messages' : []
    }


    # test if website url is valid
    try:
        page = fetch_page(obj.website)
        if page:
            result['scores'] += 1
    except:
        result['messages'].append((message_levels.ERROR, 'Error while loading website'))


    # test if scm url is valid
    # todo: there's no easy way to do this

    # test if scm type is set
    if obj.scmtype > SCM_UNKNOWN:
        result['scores'] += 1
    else:
        result['messages'].append((message_levels.ERROR, 'Select reasonable value for %s' % obj._meta.get_field('scmtype').verbose_name))

    # test bug format string
    try:
        text = obj.bugurl % 1
        result['scores'] += 1
    except:
        result['messages'].append((message_levels.ERROR, 'Field %s is not a valid format string' % obj._meta.get_field('bugurl').verbose_name))

    # test tracker type is set
    if obj.bugtype != BUG_TYPE_UNKNOWN:
        result['scores'] += 1
    else:
        result['messages'].append((message_levels.ERROR, 'Select reasonable value for %s' % obj._meta.get_field('bugtype').verbose_name))

    # warn: changelog
    if not obj.changelog:
        result['messages'].append((message_levels.WARNING, "Changelog name is missing. Most packages provide a CHANGELOG file."))

    return result


def test_if_package_version_verified(obj):
    """
        Test if all required data is present and the PackageVersion
        can safely be moved to VERIFIED.

        @obj - PackageVersion object.
        @return - { 'scores' - int, 'messages' : list of (level, message) }
    """

    # NB: this is BAD but STATUS_ is used in so many places.
    from models import STATUS_VERIFIED, STATUS_ASSIGNED
    from django.contrib.messages import constants as message_levels

    result = {
        'scores' : 0,
        'messages' : []
    }

    if obj.scmid and (obj.scmid != TAG_NOT_FOUND):
        result['scores'] += 1
    else:
        result['messages'].append((message_levels.ERROR, "Specify SCM branch/tag/commit!"))

    if obj.released_on:
        result['scores'] += 1
    else:
        result['messages'].append((message_levels.ERROR, "Fill the Released On date!"))

    if obj.download_url:
        result['scores'] += 1
    else:
        result['messages'].append((message_levels.ERROR, "Download URL is empty!"))


    if obj.package.status == STATUS_VERIFIED:
        result['scores'] += 1
    else:
        result['messages'].append((message_levels.ERROR, "Package status is not VERIFIED!"))

    if obj.status != STATUS_ASSIGNED:
        result['scores'] += 1
    else:
        result['messages'].append((message_levels.ERROR, "Needs manual inspection!"))

    return result

def get_status(scores, expected, status_match, status_not_match):
    """
        Simple status helper.
    """

    if scores == expected:
        return status_match
    else:
        return status_not_match


def which_tmp_dir():
    """
        Return the path to temporary directory
        where sources and packages are kept.
    """

    return tempfile.gettempdir()

def change_rate(new, old):
    """
        Return the change rate in % between
        @old - int, to @new - int
    """
#TODO: make this a similarity index based on difflib or Levenshtein
    if (new is None) or (old is None):
        return None

    if old == 0:
        if new > 0:
            return 100
        elif new == 0:
            return 0
    else:
        return 100*(new - old)/old

def which_severity(change_rate):
    """
        Return LOW/MEDIUM/HIGH based on how much
        the package changed.

        @change_rate - int - %
    """
#TODO: fix this (revert it) once similarity index is implemented
# index of 100% means equals, 0% means totally different
    if change_rate is None:
        return SEVERITY_UNKNOWN

    if (-30 <= change_rate) and (change_rate <= 30):
        return SEVERITY_LOW

    if ((-70 <= change_rate) and (change_rate < -30)) or \
       ((30 < change_rate) and (change_rate <= 70)):
        return SEVERITY_MEDIUM

    if (change_rate < -70) or (change_rate > 70):
        return SEVERITY_HIGH



# which file extensions are recognized
SUPPORTED_ARCHIVES = ['.tar.gz', 'tgz', '.tar.bz2', 'tbz2', '.zip', '.jar', '.gem']

def get_extract_func(url):
    """
        @return - return a callback to extract the tarball contents
    """
    if (url.find('tar.gz') > -1 ) or \
        url.endswith('.tar.bz2') or \
        url.endswith('tgz') or \
        url.endswith('tbz2') or \
        (url.find('/tarball/') > -1) or \
        (url.find('/legacy.tar.gz/') > -1):
        return tar.untar
    elif url.endswith('.zip') or \
        url.endswith('.jar') or \
        (url.find('/legacy.zip/') > -1) or \
        (url.find('/zip/') > -1) or \
        (url.find('/zipball/') > -1): # github zip from commit #
        return tar.unzip
    elif url.endswith('.gem'):
        return tar.extract_gem

    return None

def compile_changelog(package_xml):
    """
        Parse a package.xml file from a PEAR package
        and write a Changelog file in the same dir.
        package.xml contains the changelog in XML form.

        @package_xml - path to the file.
    """

    try:
        # NB: The name is Changelog.php which is unlikely to coincide with a Changelog
        # file distributed in the tarball itself.
        changelog_name = os.path.join(os.path.dirname(package_xml), 'Changelog.php')

        # rewrite the file if it already exists
        changelog_text = open(changelog_name, 'w')

        dom = parse(package_xml)
        changelog = dom.getElementsByTagName("changelog")
        if changelog:
            changelog = changelog[0]
        else:
            return

        for release in changelog.childNodes:
            if release.nodeName != u'release':
                continue

            version = release.getElementsByTagName("version")[0]
            release_version = version.getElementsByTagName("release")[0].firstChild.wholeText
            api_version = version.getElementsByTagName("api")[0].firstChild.wholeText

            stability = release.getElementsByTagName("stability")[0]
            release_stability = stability.getElementsByTagName("release")[0].firstChild.wholeText
            api_stability = stability.getElementsByTagName("api")[0].firstChild.wholeText

            date = release.getElementsByTagName("date")[0].firstChild.wholeText
            notes = release.getElementsByTagName("notes")[0].firstChild.wholeText

            text = """
%s - Release %s (%s) / API %s (%s)
--------------------------------------------------
%s
""" % (date, release_version, release_stability, api_version, api_stability, notes)

            changelog_text.write(text.encode('UTF8', 'replace'))
    finally:
        changelog_text.close()

def download_extract_commit(pv, dirname, generate_changelog=False):
    """
        @pv - PackageVersion object
        @dirname - directory of local git repo

        Downloads a tarball, extracts to @dirname
        and commits into local git repository.
    """

    os.chdir(dirname)

#    import sys
#    print os.getcwd()
#    print sys.path

    #check if the same tag already exists and skip the import
    version = pv.version.replace(" ", "_")
    version = version.replace(".", "\.")
    if os.system('git tag | grep "^%s$"' % version) == 0: # tag alredy exists
        return

    extract_func = get_extract_func(pv.download_url)

    if not extract_func:
        raise Exception('No extract_func for %s' % pv.download_url)

    # remove all files from previous tag.
    # we're doing this because tags are not imported in sequence.
    for p in os.listdir(dirname):
        # skip git directory
        if (p == ".git") and os.path.isdir(p):
            continue

        if os.path.isfile(p):
            os.remove(p)

        if os.path.isdir(p):
            shutil.rmtree(p, True) # ignore errors

    local_fname = None

    # import grabber here, because urlgrabber is not installed on OpenShift
    # and outside try/finally
    try:
        import grabber
    except:
        from difio import grabber

    try:
        local_fname = grabber.download_file(pv.download_url, dirname)
        extract_func(local_fname, dirname)

        # some packages, e.g. django-leaflet-storage
        # ship with git submodules in the tarball, represented via .git *files*
        # this breaks tarball extraction so remove .git *files* if present
        for (dirpath, dirs, files) in os.walk(dirname):
            for f in files:
                if (f == ".git"):
                    os.remove(os.path.join(dirpath, f))

        if generate_changelog:
            compile_changelog(os.path.join(dirname, 'package.xml'))
    finally:
        if local_fname:
            grabber.remove_file(local_fname)
        else:
            raise Exception("Failed to download %s" % pv.download_url)

    # extraction is done, now commit
    # NB: extract_func() will extract everything into the dirname
    # and remove any parent directories from the archive so that diff works
    if os.system("git add .") != 0:
        raise Exception("FAILED: git add %s/%s" % (dirname, pv.__unicode__()))

    # this may fail if nothing has changed
    # use -a to commit removed files
    cmdline = "git commit --allow-empty -a -m 'Import %s' --author='Difio <info@nospam.dif.io>'" % pv.__unicode__()
    ret_code = os.system(cmdline)
    if ret_code not in [0, 1]:
        raise Exception("FAILED: git commit %s/%s - return value %d" % (dirname, pv.__unicode__(), ret_code))

    if os.system("git tag '%s'" % pv.version.replace(" ", "_")) != 0:
        raise Exception("FAILED: git tag %s/%s" % (dirname, pv.__unicode__()))


def files_in_dir(dirname):
    """
        Walk all files in @dirname and return the filenames.

        todo: optimize walking all files
    """
    dirfiles = []

    for (path, dirs, files) in os.walk(dirname):
        for f in files:
            fname = os.path.join(path, f)
            dirfiles.append(fname)

    return dirfiles

def email_check(request):
    """
        Check if the currently logged user has provided an email address.

        @return - bool - True if email is present, False otherwise.

    """
    from django.contrib import messages

    if not request.user.email:
        messages.warning(request, "You have not provided an email address!")
        return False
    else:
        email = request.user.email
        at_pos = email.find('@')
        dot_pos = email[at_pos+1:].find('.') # search for dots after @
        if -1 in [at_pos, dot_pos]:
            messages.warning(request, "Email address does not appear to be valid!")
            return False

    return True


def checkout_or_pull(dirname, scmurl, CLONE_CMD, PULL_CMD):
    """
        Checkout or update existing repository.

        @dirname - string - where to checkout or update
        @scmurl - string - git/hg/svn URL
        @CLONE_CMD - format string - command to clone
        @PULL_CMD - format string - command to pull
    """

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    if not os.listdir(dirname):
        # empty directory => checkout sources
        if CLONE_CMD:
            cmdline = CLONE_CMD % (scmurl, dirname)
            if os.system(cmdline) != 0:
                raise Exception("FAILED: %s" % cmdline)

        os.chdir(dirname)
    else:
        # pull the latest updates
        os.chdir(dirname)

        if PULL_CMD:
            cmdline = PULL_CMD
            if os.system(cmdline) != 0:
                raise Exception("FAILED: %s in %s" % (cmdline, dirname))

def which_checkout_dir(scm_short_name, pkg_type, pkg_name, adv_id=None):
    """
        @scm_short_name - string - 'git', 'hg', etc.
        @pkg_type - int - 0, 1, etc.
        @pkg_name - string - the name of the package

        @return - string - path to local checkout
    """

    tmpdir = which_tmp_dir()
    if adv_id:
    # per advisory structure for parallel processing
        return '%s/%s-%d/%s' % (tmpdir, pkg_name, adv_id, scm_short_name)
    else:
        return '%s/%s/%d/%s' % (tmpdir, scm_short_name, pkg_type, pkg_name)

def get_bugs_query(advisory_id):
    """
        Helper. This QuerySet is used in multiple places
    """
#todo: make this Advisory.bugs. property
    from difio.models import Bug
    return Bug.objects.filter(advisory=advisory_id).order_by('number')


def get_bugs_as_html(advisory_id, is_admin=False):
    """
        Generate HTML for users and admins
    """

    from difio.models import Advisory
    from django.core.urlresolvers import reverse

    try:
        adv = Advisory.objects.filter(pk=advisory_id)[0]
    except IndexError:
        return ""

    bugs = get_bugs_query(adv.pk)

    if bugs.count() == 0:
        return "None"

    from django.shortcuts import render
    from django.core.handlers.wsgi import WSGIRequest
    from django.contrib.auth.models import AnonymousUser

    # dummy object to pass to views
    env = {
            'REQUEST_METHOD' : 'GET',
            'wsgi.input' : None,
        }
    request = WSGIRequest(env)
    request.user = AnonymousUser()

    response = render(request, 'bugs.html', 
                            {
                                'advisory_id' : adv.pk,
                                'bugs' : bugs,
                                'postUrl' : reverse('ajax_delete_bug'),
                                'is_admin' : is_admin,
                                # time delta for bug reported/closed on dates comparison
                                'start_date' : adv.old.released_on - timedelta(hours=24),
                                'end_date' : adv.new.released_on + timedelta(hours=24),
                            }
                    )

#    return html_minify(response.content)
    return response.content # latest htmlmin is worse than older versions


def get_test_dirs():
    """
        Return a list of directories commonly used for tests.

        Some operations, like API diff will skip such directories.
    """
    return [
            'SelfTest/', # pycrypto
            'test/',
            'tests/',
            't/',
            'testing/',
            'test_utils/',
            'tests_utils/',
            'testsuite/',
            'tests.py',
            'test.py',
            'test_regex.py' # Pythoin regex module
            ]
