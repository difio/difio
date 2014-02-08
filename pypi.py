#!/usr/bin/env python

################################################################################
#
#   Copyright (c) 2011-2012, Alexander Todorov <atodorov@nospam.dif.io>
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


import json
import logging
from datetime import datetime
from xml.dom.minidom import parseString
from pip.commands.search import highest_version
from utils import fetch_page, SUPPORTED_ARCHIVES
from pip.commands.search import compare_versions as pypi_compare_versions

logger = logging.getLogger(__name__)

_twisted_mappings = {
        'Twisted-Conch'  : 'Twisted Conch',
        'Twisted-Core'   : 'Twisted Core',
        'Twisted-Lore'   : 'Twisted Lore',
        'Twisted-Mail'   : 'Twisted Mail',
        'Twisted-Names'  : 'Twisted Names',
        'Twisted-News'   : 'Twisted News',
        'Twisted-Pair'   : 'Twisted Pair',
        'Twisted-Runner' : 'Twisted Runner',
        'Twisted-Web'    : 'Twisted Web',
        'Twisted-Words'  : 'Twisted Words',
}

def _other_name(name):
    """
        Sometimes name of packages on disk and in PyPI don't match.
        For example mercurial vs. Mercurial.
    """

    # 'install_name' : 'pypi_name'
    mappings = {
        'bdist-mpkg' : 'bdist_mpkg',
        'cx-Oracle' : 'cx_Oracle',
        'deform-bootstrap' : 'deform_bootstrap',
        'django-chartit' : 'django_chartit',
        'django-polymorphic' : 'django_polymorphic',
        'js.jquery-timepicker-addon' : 'js.jquery_timepicker_addon',
        'kotti-tinymce' : 'kotti_tinymce',
        'line-profiler' : 'line_profiler',
        'mercurial' : 'Mercurial',
        'prioritized-methods' : 'prioritized_methods',
        'Python-WebDAV-Library' : 'Python_WebDAV_Library',
        'pyramid-beaker' : 'pyramid_beaker',
        'pyramid-debugtoolbar' : 'pyramid_debugtoolbar',
        'pyramid-deform' : 'pyramid_deform',
        'pyramid-mailer' : 'pyramid_mailer',
    }

    for k in _twisted_mappings.keys():
        mappings[k] = _twisted_mappings[k]

    if mappings.has_key(name):
        return mappings[name]
    else:
        return name

def get_release_date(package, version, data = None):
    """
        Return the released_on date for this version.
    """

    pkg_name = _other_name(package)

    if not data:
        data = fetch_page("https://pypi.python.org/pypi/%s/%s/json" % (pkg_name, version))
        data = json.loads(data)

    if data.has_key('urls') and (len(data['urls']) >= 1) and data['urls'][0].has_key('upload_time'):
        return datetime.strptime(str(data['urls'][0]['upload_time']), '%Y-%m-%dT%H:%M:%S')
    else:
        return None

def get_download_url(package, version, data = None):
    """
        Return URL to download the package.
    """

    # Twisted packages are many and follow a pattern but not hosted on PyPI
    if package in _twisted_mappings.keys():
        sub_package = package.split('-')[1]
        main_ver = '.'.join(version.split('.')[:2])
        return 'http://twistedmatrix.com/Releases/%s/%s/Twisted%s-%s.tar.bz2' % (sub_package, main_ver, sub_package, version)

    pkg_name = _other_name(package)

    if not data:
        data = fetch_page("https://pypi.python.org/pypi/%s/%s/json" % (pkg_name, version))
        data = json.loads(data)

    if data.has_key('urls'):
        for file in data['urls']:
            # consider only source packages
            if file['packagetype'] == 'sdist':
                return file['url']

    if data.has_key('info') and data['info'].has_key('download_url'):
        url = data['info']['download_url']
        for ext in SUPPORTED_ARCHIVES:
            if url.endswith(ext):
                return url

    return None


def get_latest(package, last_checked=None):
    """
        Get the latest version of a package

        @return - version, released_on
    """

    pkg_name = _other_name(package)

    # fetch JSON only using package name. Will fetch latest version
    versions = fetch_page("https://pypi.python.org/pypi/%s/json" % pkg_name, last_modified=last_checked)

    if versions is None: # NB: empty string is not None but will fail the check
        return 304, 304

    versions = json.loads(versions)

    if (not versions):
        logger.error("Can't find latest version - %s" % package)
        return "", None

    latest_ver = versions['info']['version']
    release_date = get_release_date(pkg_name, latest_ver, versions)

    return latest_ver, release_date

def get_url(package, version=None):
    """
        Return homepage, repo, bugtracker URLs for a package
    """
    urls = {
            'homepage'   : '',
            'repository' : '',
            'bugtracker' : '',
        }

    # Twisted packages are many and follow a pattern but not hosted on PyPI
    if package in _twisted_mappings.keys():
        return {
            'homepage' : 'http://twistedmatrix.com/trac/wiki/%s' % package.replace('-', ''),
            'repository' : 'svn://svn.twistedmatrix.com/svn/Twisted/trunk',
            'bugtracker' : 'http://twistedmatrix.com/trac/ticket/%d',
        }

    pkg_name = _other_name(package)

    if not version:
        version, released_on = get_latest(pkg_name)

    release_data = fetch_page("https://pypi.python.org/pypi/%s/%s/json" % (pkg_name, version))
    release_data = json.loads(release_data)

    if (not release_data):
        logger.error("Can't find URL for %s-%s" % (package, version))
        return urls

    # home page
    if release_data['info'].has_key('home_page') and release_data['info']['home_page']:
        urls['homepage'] = release_data['info']['home_page']
    elif release_data['info'].has_key('package_url'):
        urls['homepage'] = release_data['info']['package_url']

    # bugtracker
    if release_data['info'].has_key('bugtrack_url') and release_data['info']['bugtrack_url']:
        urls['bugtracker'] = release_data['info']['bugtrack_url']

    return urls

def compare_versions(ver1, ver2):
    return pypi_compare_versions(ver1, ver2)

def get_latest_from_rss():
    """
        Return list of (name, version, released_on) of the
        latest versions of packages added to the index.
    """
    rss = fetch_page("https://pypi.python.org/pypi?:action=rss", False)
    dom = parseString(rss)
    result = []
    for item in dom.getElementsByTagName("item"):
        try:
            title = item.getElementsByTagName("title")[0]
            pub_date = item.getElementsByTagName("pubDate")[0]

            (name, version) = title.firstChild.wholeText.split(" ")
            released_on = datetime.strptime(pub_date.firstChild.wholeText, '%d %b %Y %H:%M:%S GMT')
            result.append((name, version, released_on))
        except:
            continue

    return result


if __name__ == "__main__":
    unsorted = ['1.2.4', '1.2.4c1', '1.2.4b3']
    print "Unsorted:"
    for v in unsorted:
        print v

    unsorted.sort(compare_versions)
    print "Sorted:"
    for v in unsorted:
        print v


    for name in ["difio-openshift-python", 'mercurial', 'roundup']:
        latest, released_on = get_latest(name)
        urls = get_url(name, latest)
        print latest, released_on, type(released_on), urls

    name = 'difio-openshift-python'
    for ver in ['2.0']:
        print get_release_date(name, ver), name, ver

    print "Download URL is: ", get_download_url('roundup', '1.4.10')
    print "Download URL is: ", get_download_url('Mercurial', '2.2.2')
    print "Download URL is: ", get_download_url('Django', '1.3.4')

    latest = get_latest_from_rss()
    from pprint import pprint
    pprint(latest)
