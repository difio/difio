#!/usr/bin/env python

################################################################################
#
#   Copyright (c) 2012, Svetlozar Argirov <zarrro [AT] gmail.com>
#   Copyright (c) 2012-2013, Alexander Todorov <atodorov@nospam.dif.io>
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
import json
import httplib
import logging
from utils import fetch_page
from datetime import datetime
from BeautifulSoup import BeautifulSoup

logger = logging.getLogger(__name__)

def get_pkg_descr(package, version=None, last_modified=None):
    """
        Get package description from registry
    """
    json_data = fetch_page('http://registry.npmjs.org/%s' % package, last_modified=last_modified)

    if json_data is None: # NB: empty string is not None but will fail the check
        return None
    else:
        return json.loads(json_data)

def get_release_date(package, version, data = None):
    """
        Return the released_on date for this version.
    """

    if not data:
        data = get_pkg_descr(package)

    if data.has_key('time') and data['time'].has_key(version):
        released_on = data['time'][version]
        released_on = datetime.strptime(released_on, '%Y-%m-%dT%H:%M:%S.%fZ')
    else:
        released_on = None

    return released_on

def get_download_url(package, version, data = None):
    """
        Return download URL for this version.
    """

    if not data:
        data = get_pkg_descr(package)

    if data.has_key('versions') and data['versions'].has_key(version):
        verinfo = data['versions'][version]
        if verinfo.has_key('dist') and verinfo['dist'].has_key('tarball'):
            return verinfo['dist']['tarball']

    return None

def get_latest(package, last_checked=None):
    """
        Get the latest version of a package
    """
    data = get_pkg_descr(package, last_modified=last_checked)

    if data is None: # NB: empty string is not None but will fail the check
        return 304, 304

    latest_ver = data['dist-tags']['latest']
    released_on = get_release_date(package, latest_ver, data)

    return latest_ver, released_on


def get_url(package, version=None):
    """
        Return homepage, repo, bugtracker URLs for a package
    """
    urls = {
            'homepage'   : "https://npmjs.org/package/" + package,
            'repository' : '',
            'bugtracker' : '',
        }

    try:
        data = get_pkg_descr(package, version)

        version = version or data['dist-tags']['latest']
        descr = data['versions'][version]

        if descr.has_key('bugs') and descr['bugs'].has_key('url'):
            urls['bugtracker'] = descr['bugs']['url']

        if descr.has_key('repository') and descr['repository'].has_key('url'):
            repository_url = descr['repository']['url']
            urls['repository'] = repository_url

            if repository_url.find('github.com') > -1:
                repository_url = repository_url.replace('git://', 'http://').replace('.git', '')
                urls['homepage'] = repository_url

        if descr.has_key('homepage'):
            hp = descr['homepage']
            if type(hp) == type([]):
                if len(hp) == 1:
                    urls['homepage'] = hp[0]
                else:
                    urls['homepage'] = ', '.join(hp)
            else:
                urls['homepage'] = hp
        elif descr.has_key('url'):
            urls['homepage'] =  descr['url']
    except:
        pass

    return urls

class Semver:
    """
        Represent a npm version. For version descriptions see :
            https://github.com/isaacs/node-semver
            http://npmjs.org/doc/semver.html
    """
    VER_RE = re.compile('^[=v]?(?P<maj>\d+)\.(?P<min>\d+)\.(?P<patch>\d+)(?P<build>-\d+)?(?P<tag>\S+)?')
    def __init__(self,version): # FALSE NEGATIVE
        self.major = None
        self.minor = None
        self.patch = None
        self.build = None
        self.tag = None
        mo = self.VER_RE.match(version)
        if not mo:
            return
        self.major = int(mo.group('maj'))
        self.minor = int(mo.group('min'))
        self.patch = int(mo.group('patch'))
        if mo.group('build'):
            self.build = int(mo.group('build')[1:])
        if mo.group('tag'):
            self.tag = mo.group('tag')
    def compare(self, other):
        # major
        if self.major < other.major :
            return -1
        if self.major > other.major :
            return 1
        # minor
        if self.minor < other.minor :
            return -1
        if self.minor > other.minor :
            return 1
        # patch
        if self.patch < other.patch :
            return -1
        if self.patch > other.patch :
            return 1
        # build numbers
        if self.build :
            # having a build number > no build number
            if not other.build :
                return 1
            if self.build < other.build :
                return -1
            if self.build > other.build :
                return 1
        if not self.build and other.build :
            return -1
        # tags compared , the one without tag is greater
        if self.tag and not other.tag :
            return -1
        if other.tag and not self.tag :
            return 1
        # if both have tags, compare lexicographically
        if self.tag < other.tag :
            return -1
        if self.tag > other.tag :
            return 1
        return 0

def compare_versions(ver1, ver2):
    return Semver(ver1).compare(Semver(ver2))

def get_latest_from_rss():
    """
        Return list of (name, version, released_on) of the
        latest versions of packages added to the index.
    """
    # NB: limit=50 is hardcoded upstream
    rss = fetch_page("http://registry.npmjs.org/-/rss?descending=true&limit=50", decode=False)
    soup = BeautifulSoup(rss)
    result = []

    for item in soup.findAll("item"):
        try:
            pub_date = item.pubdate.text

            (name, version) = item.title.text.split("@")

            # NB: <pubDate>2012-06-27T20:29:22.550Z</pubDate>
            # Python doesn't have format string for miliseconds so strip it out
            released_on = datetime.strptime(pub_date.split('.')[0], '%Y-%m-%dT%H:%M:%S')

            result.append((name, version, released_on))
        except:
            continue

    return result

if __name__ == "__main__":
    # according to http://npmjs.org/doc/json.html
    #  0.1.2-7 > 0.1.2-7-beta > 0.1.2-6 > 0.1.2 > 0.1.2beta
    unsorted = [
        '1.3.5', '4.5.222', '0.0.1',
        '0.1.2-7-beta' , '0.1.2beta', '0.1.2-7', '0.1.2', '0.1.2-6'
        ]
    print "Unsorted:"
    for v in unsorted:
        print v

    unsorted.sort(compare_versions)
    print "Sorted:"
    for v in unsorted:
        print v
    
    print
    
    for name in ["less", "difio-dotcloud-nodejs", "markdown-js"]:
        latest, released_on = get_latest(name)
        urls = get_url(name)
        print latest, released_on, type(released_on), urls

    name = 'xmlhttprequest'
    for ver in ['1.0.0', '1.2.0', '1.2.1', '1.2.2', '1.3.0']:
        print get_release_date(name, ver), name, ver

    print "Download URL is ", get_download_url('underscore', '1.2.2')

    latest = get_latest_from_rss()
    from pprint import pprint
    pprint(latest)
