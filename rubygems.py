#!/usr/bin/env python

################################################################################
#
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


import json
import logging
from utils import fetch_page
from datetime import datetime

logger = logging.getLogger(__name__)

def get_download_url(package, version, data = None):
    """
        Return download URL.
        NB: this is the gem_uri from the main record.
        In case of JRuby it will return wrong URL.
        The proper one is XXX-VERSION-java.gem. See neo4j-enterprise.

        TODO: We need to store "java" inside version string.
    """

    return "https://rubygems.org/gems/%s-%s.gem" % (package, version)


def get_release_date(package, version, data = None):
    """
        Return the released_on date for this version.
    """

    if not data:
        json_data = fetch_page('https://rubygems.org/api/v1/versions/%s.json' % package)
#        json_data = json_data.decode('UTF-8')
        data = json.loads(json_data)

    for ver in data:
        if ver['number'] == version:
            return datetime.strptime(ver['built_at'], '%Y-%m-%dT%H:%M:%SZ')

    return None

def get_latest(package, last_checked=None):
    """
        Get the latest version of a package
    """
    json_data = fetch_page('http://rubygems.org/api/v1/versions/%s.json' % package, last_modified=last_checked)

    if json_data is None: # NB: empty string is not None but will fail the check
        return 304, 304

    data = json.loads(json_data)

    for version in data: # i in range(0, len(data)):
        if version['prerelease']:
            continue
        else:
            return version['number'], get_release_date(package, version['number'], data)

    # in case there are only pre-release versions
    return None, None

def get_url(package, version=None):
    """
        Return homepage, repo, bugtracker URLs for a package
    """
    urls = {
            'homepage'   : '',
            'repository' : '',
            'bugtracker' : '',
        }

    json_data = fetch_page('https://rubygems.org/api/v1/gems/%s.json' % package)
#    json_data = json_data.decode('UTF-8')
    data = json.loads(json_data)

    if data.has_key('homepage_uri'):
        urls['homepage'] = data['homepage_uri']
    else:
        urls['homepage'] = data['project_uri']

    if data.has_key('bug_tracker_uri') and data['bug_tracker_uri']:
        urls['bugtracker'] = data['bug_tracker_uri']

    if data.has_key('source_code_uri') and data['source_code_uri']:
        urls['repository'] = data['source_code_uri']

    return urls

def compare_versions(ver1, ver2):
    """
        Based on:
        http://groups.google.com/group/gemcutter/msg/516151c8cdd02721?dmode=source

        See also:
        http://groups.google.com/group/gemcutter/browse_frm/thread/2218032b82053868
        http://groups.google.com/group/gemcutter/browse_thread/thread/d0283c38b817ca1

        See also version.rb.

        NB: if package changes the versioning format, e.g. "X.1a" vs "X.1.a" then
        "1a" > "1.a" which is a BUG but we should not be comparing preprelease versions anyway.
    """

    ver1_a = ver1.split('.')
    ver2_a = ver2.split('.')

    lhsize = len(ver1_a)
    rhsize = len(ver2_a)
    limit = max(lhsize, rhsize)

    for i in range(0, limit):
        try:
            lhs = ver1_a[i]
        except IndexError:
            lhs = '0'

        try:
            rhs = ver2_a[i]
        except IndexError:
            rhs = '0'

        # do not compare dots
        if "." in [lhs, rhs]:
            continue

        # if both are digits or
        # both are not digits
        if (lhs.isdigit() and rhs.isdigit()) or \
            ((not lhs.isdigit()) and (not rhs.isdigit())) :

            # first try comparing as integers
            try:
                result = cmp(int(lhs), int(rhs))
            except ValueError:
                # if it doesn't work then compare as strings
                result = cmp(lhs, rhs)

            # don't abort comparison if equal
            if result != 0:
                return result
        else:  # one is not digit
            for j in range(0, max(len(lhs), len(rhs))):
                try:
                    l = lhs[j]
                except IndexError:
                    return 1

                try:
                    r = rhs[j]
                except IndexError:
                    return -1

                if l != r:
                    return cmp(l, r)

    return 0

def get_latest_from_rss():
    """
        @return - list of (name. version, released_on)
    """
    data = fetch_page("https://rubygems.org/api/v1/activity/just_updated.json")
    latest = json.loads(data)
    result = []

    for gem in latest:
# NB: not implemented
# see https://github.com/rubygems/rubygems.org/issues/536
#        if gem['prerelease']:
#            continue

        # don't add prerelease software
        (latest_ver, released_on) = get_latest(gem['name'])

#todo: this JSON give more info like GitHub URLs import from here 
# and kill some messages

        if latest_ver == gem['version']:
            # RubyGems.org doesn't provide date of release
            result.append((gem['name'], gem['version'], released_on))

    return result

if __name__ == "__main__":
    latest = get_latest_from_rss()
    from pprint import pprint
    pprint(latest)

    unsorted = ['0.3.2.1.1', '0.3.2.1', '0.3.2.1a', '0.3.2.1b', '0.3.2', '0.3.2a', '0.3.1', '0.3.1a', '0.3', '0.4', '0.1']
    print "Unsorted:"
    for v in unsorted:
        print v

    unsorted.sort(compare_versions)
    print "Sorted:"
    for v in unsorted:
        print v

    for name in ["rack-mount", 'actionmailer']:
        latest, released_on = get_latest(name)
        urls = get_url(name)
        print latest, released_on, type(released_on), urls

    name = 'rack-mount'
    for ver in ['0.7.4', '0.8.0', '0.8.1', '0.8.2', '0.8.3']:
        print get_release_date(name, ver), name, ver
