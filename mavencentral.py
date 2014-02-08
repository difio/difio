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
from utils import fetch_page
from datetime import datetime
from xml.dom.minidom import parseString

def _groupid_artifactid(name):
    """
        @name - string - package name of the form groupid:artifactid, e.g. junit:junit
        @return - list - [groupid, artifactid]
    """
    return name.split(':')


def get_release_date(package, version, data = None):
    """
        Return the released_on date for this version.
    """
    [groupid, artifactid] = _groupid_artifactid(package)

    if not data:
        data = fetch_page('http://search.maven.org/solrsearch/select?q=g:"%s"+AND+a:"%s"+AND+v:"%s"&wt=json' %
                        (groupid, artifactid, version)
                )
        data = json.loads(data)

    released_on = data['response']['docs'][0]['timestamp']
    released_on = datetime.fromtimestamp(released_on/1000)

    return released_on


def get_download_url(package, version, data = None):
    """
        Return URL to download the package.
    """
    [groupid, artifactid] = _groupid_artifactid(package)

    return "http://search.maven.org/remotecontent?filepath=%s/%s/%s/%s-%s-sources.jar" % (groupid.replace('.', '/'), artifactid, version, artifactid, version)


def get_latest(package, last_checked=None):
    """
        Get the latest version of a package

        @return - version, released_on
    """
    [groupid, artifactid] = _groupid_artifactid(package)

    data = fetch_page('http://search.maven.org/solrsearch/select?q=g:"%s"+AND+a:"%s"&wt=json&core=gav' % (groupid, artifactid), last_modified=last_checked)

    if data is None: # NB: empty string is not None but will fail the check
        return 304, 304

    data = json.loads(data)

    latest_ver = None
    latest_timestamp = 0

    for release in data['response']['docs']:
        if release['timestamp'] > latest_timestamp:
            latest_timestamp = release['timestamp']
            latest_ver = release['v']

    released_on = datetime.fromtimestamp(latest_timestamp/1000)
    return latest_ver, released_on

def get_url(package, version=None):
    """
        Return homepage, repo, bugtracker URLs for a package
    """
    urls = {
            'homepage'   : '',
            'repository' : '',
            'bugtracker' : '',
        }
    [groupid, artifactid] = _groupid_artifactid(package)

    if not version:
        version, released_on = get_latest(pakage)

    pom_xml = fetch_page("http://search.maven.org/remotecontent?filepath=%s/%s/%s/%s-%s.pom" % 
                            (groupid.replace('.', '/'), artifactid, version, artifactid, version)
                )
    dom = parseString(pom_xml)

    # search for homepage
    for url in dom.getElementsByTagName('url'):
        if not urls['homepage']:
            urls['homepage'] = url.firstChild.wholeText

        # prefer github URLs
        if url.firstChild.wholeText.find('github.com') > -1:
            urls['homepage'] = url.firstChild.wholeText
            break

    # search for code repository
    for conn in dom.getElementsByTagName('connection'):
        if not urls['repository']:
            urls['repository'] = conn.firstChild.wholeText
            # format is scm:type:URL or scm:type:scm:type:URL so remove prefix
            while urls['repository'].find('scm:') > -1:
                urls['repository'] = ":".join(urls['repository'].split(':')[2:])
            break

    # search for bugtracker URL
    for tracker in dom.getElementsByTagName('issueManagement'):
        for url in tracker.getElementsByTagName('url'):
            if not urls['bugtracker']:
                urls['bugtracker'] = url.firstChild.wholeText
                break

    return urls

def compare_versions(ver1, ver2):
    raise NotImplementedError

def get_latest_from_rss():
    """
        Return list of (name, version, released_on) of the
        latest versions of packages added to the index.

    NB: See https://getsatisfaction.com/sonatype/topics/rss_feeds_for_artifact_group_updates
        looks like this feature is not well maintained or publicly advertised.

    """
# 404
#    rss = fetch_page("http://search.maven.org/remotecontent?filepath=rss.xml")
    rss = fetch_page("http://repo1.maven.org/maven2/rss.xml")

    dom = parseString(rss)
    result = []
    for item in dom.getElementsByTagName("item"):
        try:
            title = item.getElementsByTagName("title")[0]
            pub_date = item.getElementsByTagName("pubDate")[0]

            (gid, aid, version) = title.firstChild.wholeText.split(":")
            released_on = datetime.strptime(pub_date.firstChild.wholeText, '%a, %d %b %Y %H:%M:%S -0500')
            result.append(("%s:%s" % (gid, aid), version, released_on))
        except:
            continue

    return result



if __name__ == "__main__":
    for name in ["commons-codec:commons-codec", "antlr:antlr", "commons-collections:commons-collections"]:
        latest, released_on = get_latest(name)
        print name, latest, released_on, type(released_on)

    print
    print

    for name in ["junit:junit", "cglib:cglib-nodep", "org.apache.commons:commons-io"]:
        latest, released_on = get_latest(name)
        urls = get_url(name, latest)
        print name, latest, released_on, type(released_on), urls

    print
    print

    name = 'junit:junit'
    for ver in ['4.8', '4.8.2', '4.10']:
        print get_release_date(name, ver), name, ver

    print
    print

    print "Download URL is: ", get_download_url('junit:junit', '4.9')
    print "Download URL is: ", get_download_url('cglib:cglib-nodep', '2.2')
    print "Download URL is: ", get_download_url('org.apache.commons:commons-io', '1.3.2')

    latest = get_latest_from_rss()
    from pprint import pprint
    pprint(latest)
