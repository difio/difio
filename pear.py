#!/usr/bin/env python

################################################################################
#
#   Copyright (c) 2012, Alexander Todorov <atodorov@nospam.dif.io>
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
import httplib
from utils import fetch_page
from datetime import datetime
from xml.dom.minidom import parseString

def get_release_date(package, version, data = None):
    """
        Return the released_on date for this version.
    """
    xml = fetch_page("http://pear.php.net/rest/r/%s/%s.xml" % (package.lower(), version), False).strip()
    dom = parseString(xml)
    released_on = dom.getElementsByTagName("da")[0]
    return datetime.strptime(released_on.firstChild.wholeText, '%Y-%m-%d %H:%M:%S')

def get_download_url(package, version, data = None):
    """
        Return the download URL for this version.
    """
    return "http://download.pear.php.net/package/%s-%s.tgz" % (package, version)


def get_latest(package, last_checked=None):
    """
        Get the latest version of a package
    """
    version = fetch_page("http://pear.php.net/rest/r/%s/latest.txt" % package.lower(), last_modified=last_checked)
    if version is not None:  # NB: empty string is not None but will fail the check
        version = version.strip()
    else:
        return 304, 304

    released_on = get_release_date(package, version)
    return version, released_on

def get_url(package, version=None):
    """
        Return homepage, repo, bugtracker URLs for a package.
        All PEARs in pear.php.net are centrally controlled and hosted.
    """
    urls = {
            'homepage'   : 'https://github.com/pear/%s' % package,
            'repository' : 'git://github.com/pear/%s.git' % package,
            'bugtracker' : 'http://pear.php.net/bugs/bug.php?id=%d',
        }

    return urls

def compare_versions(ver1, ver2):
    return 0


def get_latest_from_rss():
    """
        Return list of (name, version, released_on) of the
        latest versions of packages added to the index.
    """
    rss = fetch_page("http://pear.php.net/feeds/latest.rss")
    dom = parseString(rss)
    result = []
    for item in dom.getElementsByTagName("item"):
        try:
            title = item.getElementsByTagName("title")[0]
            pub_date = item.getElementsByTagName("dc:date")[0]

            (name, version) = title.firstChild.wholeText.split(" ")
            # NB: PEAR provides a timezone offset but we consider all dates in UTC
            released_on = datetime.strptime(pub_date.firstChild.wholeText, '%Y-%m-%dT%H:%M:%S-05:00')
            result.append((name, version, released_on))
        except:
            continue

    return result


if __name__ == "__main__":
    for name in ["PHP_CodeSniffer"]:
        latest, released_on = get_latest(name)
        urls = get_url(name)
        print latest, released_on, type(released_on), urls

    for name, ver in [('DB', '1.7.10'), ('HTTP_Request', '1.2.2')]:
        try:
            print get_release_date(name, ver), name, ver
        except:
            pass

    print "Download URL is ", get_download_url("Net_Socket", "1.0.10")
    print "Download URL is ", get_download_url("Net_Socket", "1.0.1")

    latest = get_latest_from_rss()
    from pprint import pprint
    pprint(latest)
