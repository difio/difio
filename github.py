#!/usr/bin/env python

################################################################################
#
#   Copyright (c) 2012-2014, Alexander Todorov <atodorov@nospam.dif.io>
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
import httplib
import logging
from datetime import datetime, timedelta
from utils import which_tag, fetch_page

try:
    from settings import GITHUB_APP_ID, GITHUB_API_SECRET
    settings_imported = True
except:
    # used for local testing
    settings_imported = False

#### package distribution functions

def get_download_url_from_tag(package, version, data = None):
    """
        Return the download URL for a given version (which is tag).

        @package - :user/:repo combination
    """
    tags = get_tags(package, package)
    this_ver = which_tag(version, tags, package.split('/')[1])

    return "https://codeload.github.com/%s/tar.gz/%s" % (package, this_ver)

def get_download_url_from_commit(package, commit):
    """
        Return the download URL for this commit

        @package - :user/:repo combination
        @commit - commit hash
    """
    return "https://codeload.github.com/%s/legacy.tar.gz/%s" % (package, commit)

def get_release_date_from_tag(package, version, data = None):
    """
        Return the released_on date for this version (which is a tag).

        @package - :user/:repo combination
    """

    if data is not None:
        tags = data
    else:
        tags = get_tags(package, package, True) # the result here is a list of all tag attributes

    # if PV.package.type == GitHub then PV.version is a tag name like v1.2.3
    this_ver = which_tag(version, [t['name'] for t in tags], package.split('/')[1])

    for tag in tags:
        if tag['name'] == this_ver:
            return get_release_date_from_commit(package, tag['commit']['sha'])

    return None

def get_release_date_from_commit(package, commit):
    """
        Return the release date for this commit

        @package - :user/:repo combination
        @commit - commit hash
    """
    api_url = 'https://api.github.com/repos/%s/commits/%s'
    if settings_imported:
        api_url += '?client_id=%s&client_secret=%s' % (GITHUB_APP_ID, GITHUB_API_SECRET)
    json_data = fetch_page(api_url % (package, commit))

    if json_data is None:
        return None

    data = json.loads(json_data)
    released_on = data['commit']['committer']['date']
    return datetime.strptime(released_on, '%Y-%m-%dT%H:%M:%SZ')

def get_latest_from_tag(package, last_checked=None):
    """
        Get the latest version of a package

        @package - :user/:repo
    """

    all_vers = {}

    tags = get_tags(package, package, True, last_checked)

    if tags is None: # NB: empty string is not None but will fail the check
        return 304, 304

    for t in tags:
        # in case of missing tags or github error, just continue
        try:
            # NB: here we pass the tag name as version which will match
            # itself for this_ver in get_release_date_from_tag()
            released_on = get_release_date_from_tag(package, t['name'], tags)
            all_vers[released_on] = t['name']
        except:
            pass

    # sort in descending order. highest date is first
    highest_date = sorted(all_vers.keys(), reverse=True)[0]
# from tag-name return version
    highest_ver = which_tag(all_vers[highest_date], None, package.split('/')[1], True)

    return highest_ver, highest_date

def get_url(package, version=None):
    """
        Return homepage, repo, bugtracker URLs for a package.

        @package - :user/:repo
    """
    urls = {
            'homepage'   : 'https://github.com/%s' % package,
            'repository' : 'git://github.com/%s.git' % package,
            'bugtracker' : 'https://github.com/%s/issues' % package,
        }

    return urls


#### helper functions below


def _get_user_repo(url):
    """
        Return the :user/:repo/ from a github.com url
    """
    if url.find('://github.com/') > -1:  # toplevel GitHub page
        p = url.split('/')
        return '%s/%s' % (p[3], p[4].replace('.git', ''))
    elif url.find('.github.com/') > -1:  # GitHub project pages
        p = url.split('/')
        u = p[2].split('.')[0]
        return '%s/%s' % (u, p[3])

    return None

def get_tags(url, user_repo=None, extended=False, last_modified=None):
    """
        Return all GitHub tags for this package.
        @url - string - either git checkout url or http url for the GitHub page
    """

    if user_repo is None:
        user_repo = _get_user_repo(url)

    if not user_repo:
        raise Exception("GitHub - get_tags - can't find repository for %s" % url)

    api_url = 'https://api.github.com/repos/%s/tags'
    if settings_imported:
        api_url += '?client_id=%s&client_secret=%s' % (GITHUB_APP_ID, GITHUB_API_SECRET)
    json_data = fetch_page(api_url % user_repo, last_modified=last_modified)

    if json_data is None:
        return None

    data = json.loads(json_data)

    if extended:
        return data
    else:
        try:
            result = {}
            for tag in data:
                result[tag['name']] = tag['commit']['sha']
            return result
        except:
            # in case GitHub API limit was reached then above indexing will fail
            return {}


def get_files(url):
    """
        Return a list of all files in the tree.
        Used to search for changelog.
    """

    user_repo = _get_user_repo(url)

    if not user_repo:
        raise Exception("GitHub - get_files - can't find repository for %s" % url)

    api_url = 'https://api.github.com/repos/%s/git/trees/master?recursive=1'
    if settings_imported:
        api_url += '&client_id=%s&client_secret=%s' % (GITHUB_APP_ID, GITHUB_API_SECRET)

    data = fetch_page(api_url % user_repo)
    data = json.loads(data)

    return [f['path'] for f in data['tree'] if f['type'] == 'blob']


def get_commits_around_date(repo, released_on, delta=1):
    """
        Return commits which are possible to contain a version change
        for further analysis.

        @repo - string - :user/:repo combination
        @released_on - timestamp

        @return - { 'sha' : ['patch1', 'patch2'] }
    """

    since = released_on - timedelta(days=delta)
    since = since.strftime('%Y-%m-%dT%H:%M:%S')

    until = released_on + timedelta(days=delta)
    until = until.strftime('%Y-%m-%dT%H:%M:%S')

    api_url = 'https://api.github.com/repos/%s/commits?since=%s&until=%s'
    if settings_imported:
        api_url += '&client_id=%s&client_secret=%s' % (GITHUB_APP_ID, GITHUB_API_SECRET)

    json_data = fetch_page(api_url % (repo, since, until))

    if json_data is None:
        return None

    data = json.loads(json_data)

    result = {}
    for c in data:
        for p in c['parents']:
            result[p['sha']] = []
            api_url = p['url']
            if settings_imported:
                api_url += '?client_id=%s&client_secret=%s' % (GITHUB_APP_ID, GITHUB_API_SECRET)
            commit_json = fetch_page(api_url)
            if commit_json:
                commit_data = json.loads(commit_json)
                for f in commit_data['files']:
                    if f.has_key('patch'):
                        result[p['sha']].append(f['patch'])
    return result


if __name__ == "__main__":
    from pprint import pprint

    print "------------------- COMMIT DATA -----------------------"

    commits = get_commits_around_date('difio/difio-openshift-python', datetime(2012, 02, 15))
#    pprint(commits)

    print "------------------- PACKAGE FUNCTIONS -----------------------"

    for name in ["difio/difio-openshift-python", "difio/difio-openshift-java"]:
        latest, released_on = get_latest_from_tag(name)
        urls = get_url(name, latest)
        print name, latest, released_on, type(released_on), urls

    for name, ver in [('difio/difio-openshift-python', 'v1.9'), ('difio/difio-openshift-perl', 'v0.10')]:
        released_on = get_release_date_from_tag(name, ver)
        print released_on, type(released_on), name, ver

    print "Download URL is ", get_download_url_from_tag('difio/difio-openshift-python', 'v1.9')
    print "Download URL is ", get_download_url_from_tag('difio/difio-openshift-perl', 'v0.10')


    print "------------------- COMMIT HELPER FUNCTIONS -----------------------"

    for name, commit in [('rails/arel', 'e032dab'), ('chriseppstein/compass', 'd759843')]:
        released_on = get_release_date_from_commit(name, commit)
        print released_on, type(released_on), name, commit

    print "Download URL is ", get_download_url_from_commit('rails/arel', 'e032dab')
    print "Download URL is ", get_download_url_from_commit('chriseppstein/compass', 'd759843')

    print "------------------- HELPER FUNCTIONS ------------------------"

    from utils import which_tag, which_changelog

    for url in ["http://github.com/aussiegeek/rubyzip"]:
        tags = get_tags(url)
        print url, tags

    print "------------------- TAGS AND VERSIONS -----------------------"

    url = "https://github.com/difio/difio-openshift-python"
    version = "1.7"
    vtag = which_tag(version, get_tags(url))
    reverse_version = which_tag(vtag, None, None, True)
    print version, vtag, reverse_version, url


    url = "git://github.com/ask/celery.git"
    version = "2.5.1"
    vtag = which_tag(version, get_tags(url))
    print version, vtag, url


    url = "https://github.com/ask/kombu/"
    version = "2.1.1"
    vtag = which_tag(version, get_tags(url))
    print version, vtag, url

    url = "https://github.com/nanis/Crypt-SSLeay"
    version = "0.54"
    vtag = which_tag(version, get_tags(url))
    print version, vtag, url

    print "------------------ GET FILES --------------------------------"

    for url in ["https://github.com/indexzero/TimeSpan.js"]:
        files = get_files(url)
        changelog = which_changelog(files)
        print url, changelog
