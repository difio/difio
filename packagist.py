#!/usr/bin/env python

################################################################################
#
#   Copyright (c) 2013, Alexander Todorov <atodorov@nospam.dif.io>
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
from utils import fetch_page
from datetime import datetime
from xml.dom.minidom import parseString

logger = logging.getLogger(__name__)

def get_release_date(package, version, data = None):
    """
        Return the released_on date for this version.
    """

    if not data:
        data = fetch_page("https://packagist.org/packages/%s.json" % package)
        data = json.loads(data)

    try:
        released_on = data['package']['versions'][version]['time']
        released_on = released_on[:19] # remove timezone part
        return datetime.strptime(released_on, '%Y-%m-%dT%H:%M:%S')
    except:
        raise
        return None

def get_download_url(package, version, data = None):
    """
        Return URL to download the package.
    """

    if not data:
        data = fetch_page("https://packagist.org/packages/%s.json" % package)
        data = json.loads(data)

    try:
        return data['package']['versions'][version]['dist']['url']
    except:
        return None


def get_latest(package, last_checked=None, data=None):
    """
        Get the latest version of a package

        @return - version, released_on
    """

    # fetch JSON only using package name. Will fetch latest version
    if not data:
        data = fetch_page("https://packagist.org/packages/%s.json" % package, last_modified=last_checked)

        if data is None: # NB: empty string is not None but will fail the check
            return 304, 304

        data = json.loads(data)

    if (not data):
        logger.error("Can't find latest version - %s" % package)
        return "", None

    # sort versions by date and take the most recent one

    versions = {}
    for ver in data['package']['versions'].keys():
        # skip development verions
        if ver.find('dev-') > -1:
            continue

        if ver.find('-dev') > -1:
            continue

        if ver.find('master-') > -1:
            continue

        # skip Alpha and Beta versions
#        if ver.lower().find('beta') > -1:
#            continue

#        if ver.lower().find('alpha') > -1:
#            continue

        released_on = data['package']['versions'][ver]['time'][:19] # remove timezone part
        released_on = datetime.strptime(released_on, '%Y-%m-%dT%H:%M:%S')

        versions[released_on] = ver

    # sort
    dates = versions.keys()
    dates.sort(reverse=True)

    release_date = dates[0]
    latest_ver = versions[release_date]

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

    data = fetch_page("https://packagist.org/packages/%s.json" % package)
    data = json.loads(data)

    if (not data):
        logger.error("Can't find URL for %s-%s" % (package, version))
        return urls

    if not version:
        version, released_on = get_latest(package, None, data)

    # home page
    try:
        urls['homepage'] = data['package']['versions'][version]['homepage']

        if not data['package']['repository'].endswith('.git'):
            urls['homepage'] = data['package']['repository']
    except:
        pass

    # repository
    try:
        if data['package']['repository'].endswith('.git'):
            urls['repository'] = data['package']['repository']
        else:
            urls['repository'] = data['package']['versions'][version]['source']['url']
    except:
        pass

# NB: bugtracker will automatically be filled by helpers
# b/c the format is not what we expect and
# b/c every packagist package uses GitHub or BitBucket

    return urls


def get_latest_from_rss():
    """
        Return list of (name, version, released_on) of the
        latest versions of packages added to the index.
    """
    rss = fetch_page("https://packagist.org/feeds/releases.rss", False)
    dom = parseString(rss)
    result = []
    for item in dom.getElementsByTagName("item"):
        try:
            title = item.getElementsByTagName("title")[0]
            pub_date = item.getElementsByTagName("pubDate")[0]

            (name, version) = title.firstChild.wholeText.split(" ")
            version = version.replace('(', '').replace(')', '')
            released_on = datetime.strptime(pub_date.firstChild.wholeText, '%a, %d %b %Y %H:%M:%S +0000')
            result.append((name, version, released_on))
        except:
            continue

    return result


if __name__ == "__main__":
    name = 'spoonx/sxmail'
    for ver in ['1.3.4', '1.3.3', '1.3.2']:
        print get_release_date(name, ver), name, ver

    print "Download URL is: ", get_download_url('spoonx/sxmail', '1.3.4')
    print "Download URL is: ", get_download_url('mparaiso/silex-extensions', '0.0.50')
    print "Download URL is: ", get_download_url('ezzatron/php-lcs', '1.0.3')

    for name in ["kdyby/forms-replicator", "riverline/worker-bundle", "rwoverdijk/sxmail", 'yohang/finite']:
        latest, released_on = get_latest(name)
        urls = get_url(name)
        print latest, released_on, type(released_on), urls


    latest = get_latest_from_rss()
    from pprint import pprint
    pprint(latest)
