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


import json
import httplib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def _get_user_repo(url):
    """
        Return the :user/:repo/ from a bitbucket.org url
    """
    if (url.find('://bitbucket.org') > -1) or (url.find('@bitbucket.org') > -1):
        p = url.split('/')
        return '%s/%s' % (p[3], p[4])

    return None

def get_tags(url):
    """
        Return all BitBucket tags for this package.
        @url - string - either checkout url or http url for the project page
    """

    user_repo = _get_user_repo(url)

    if not user_repo:
        raise Exception("BitBucket - get_tags - can't find repository for %s" % url)

    conn = httplib.HTTPSConnection('api.bitbucket.org')
    conn.request('GET', '/1.0/repositories/%s/tags' % user_repo)
    response = conn.getresponse()

    if (response.status != 200):
        raise Exception("BitBucket - get_tags - returned %d for %s" % (response.status, url))

    json_data = response.read().decode('UTF-8')
    data = json.loads(json_data)


    return data.keys()


def get_files_and_dirs(url, dir = ""):
    """
        Return a list of all files and dirs in the tree.
    """

    user_repo = _get_user_repo(url)

    if not user_repo:
        raise Exception("BitBucket - get_files - can't find repository for %s" % url)

    conn = httplib.HTTPSConnection('api.bitbucket.org')
    conn.request('GET', '/1.0/repositories/%s/src/tip/%s' % (user_repo, dir))
    response = conn.getresponse()

    if (response.status != 200):
        raise Exception("BitBucket - get_files - returned %d for %s" % (response.status, url))

    json_data = response.read().decode('UTF-8')
    data = json.loads(json_data)

    return [f['path'] for f in data['files']], data['directories']


def get_files(url):
    """
        Return a list of all files in the tree.
        Used for searching changelog.
    """

    files, dirs = get_files_and_dirs(url)
#todo: fix me: need to browse directories as well

    return files

if __name__ == "__main__":
    from utils import which_tag, which_changelog

    for url in ["https://bitbucket.org/runeh/anyjson", "https://bitbucket.org/simplecodes/wtforms/src"]:
        tags = get_tags(url)
        print url, tags


    print "-------------------------------------------------------------"

    url = "https://bitbucket.org/haypo/python-ptrace/"
    name = "python-ptrace"
    version = "0.6.4"
    vtag = which_tag(version, get_tags(url), name)
    print version, vtag, url


    url = "https://bitbucket.org/simplecodes/wtforms"
    version = "0.6.2"
    vtag = which_tag(version, get_tags(url))
    print version, vtag, url

    print "-------------------------------------------------------------"

    for url in ["https://bitbucket.org/simplecodes/wtforms/src", "https://bitbucket.org/haypo/python-ptrace/"]:
        files = get_files(url)
        changelog = which_changelog(files)
        print url, changelog

