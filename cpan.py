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
from utils import fetch_page
from datetime import datetime
from xml.dom.minidom import parseString

logger = logging.getLogger(__name__)

def _other_name(name):
    """
        Sometimes name of packages on disk and in CPAN don't match.
        For example GD::Graph vs GDGraph.
    """

    # 'install_name' : 'cpan_name'
    mappings = {
        'Cwd' : 'PathTools',
        'Dist::Zilla::Plugin::KwaliteeTests' : 'Dist::Zilla::Plugin::Test::Kwalitee',
        'GD::Graph' : 'GDGraph',
        'GD::Text' : 'GDTextUtil',
        'List::Util' : 'Scalar-List-Utils',
        'LWP' : 'libwww-perl',
        'Template' : 'Template::Toolkit',
        'Term::ReadKey' : 'TermReadKey',
        'XBase' : 'DBD-XBase',
        'XML::LibXML::Common' : 'XML::LibXML',
    }

    if mappings.has_key(name):
        return mappings[name]
    else:
        return name

def get_author_from_html(package, version):
    """
        Try to parse the HTML page and get the author
        for an older version.
    """
    package = _other_name(package)
    package = package.replace('::', '-')

    html = fetch_page('https://metacpan.org/release/%s' % package).split('\n')
    options = []
    for line in html:
        if line.find('<option value=') > -1:
            options.append(line.strip())

    # format is
    # <option value="ADAMK/PPI-HTML-0.01/">0.01 (2005-01-15)</option>
    for opt in options:
        author = opt.split('"')[1].split('/')[0]
        ver = opt.split('>')[1].split(' ')[0]
        if ver == version:
            return author

    return None

def get_author_from_json(package):
    """
        Return the latest author name.
    """
    package = _other_name(package)
    package = package.replace('::', '-')

    conn = httplib.HTTPConnection('api.metacpan.org')
    conn.request('GET', '/v0/release/%s' % package)
    response = conn.getresponse()

    if (response.status != 200):
        raise Exception("MetaCPAN - get_author_from_json(%s) - returned %d" % (package, response.status))

    json_data = response.read().decode('UTF-8', 'replace')
    data = json.loads(json_data)

    return data['author']


def get_release_date(package, version, data = None):
    """
        Return the released_on date for this version.
    """
    package = _other_name(package)
    package = package.replace('::', '-')

    if not data:
        # todo: this will fail if later version changed author. e.g. Dancer-1.000
        author = get_author_from_json(package)

        # need a second call to metacpan.org to fetch version specific details
        conn = httplib.HTTPConnection('api.metacpan.org')
        conn.request('GET', '/v0/release/%s/%s-%s' % (author, package, version))
        response = conn.getresponse()

        if (response.status != 200):
            # maybe authors changed. Try parse HTML
            author = get_author_from_html(package, version)
            if not author:
                raise Exception("MetaCPAN - get_release_date2 (%s, %s) - returned %d and no author" % (package, version, response.status))

            # 3rd try with the value in HTML
            conn = httplib.HTTPConnection('api.metacpan.org')
            conn.request('GET', '/v0/release/%s/%s-%s' % (author, package, version))
            response = conn.getresponse()

            if (response.status != 200):
                raise Exception("MetaCPAN - get_release_date3 (%s, %s) - returned %d" % (package, version, response.status))

        json_data = response.read().decode('UTF-8')
        data = json.loads(json_data)

    if data.has_key('date'):
        return datetime.strptime(data['date'], '%Y-%m-%dT%H:%M:%S')
    else:
        return None

def get_download_url(package, version, data = None):
    """
        Return the download URL for this version.
    """
    package = _other_name(package)
    package = package.replace('::', '-')

    if not data:
        # todo: this will fail if later version changed author. e.g. Dancer-1.000
        author = get_author_from_json(package)

        # need a second call to metacpan.org to fetch version specific details
        conn = httplib.HTTPConnection('api.metacpan.org')
        conn.request('GET', '/v0/release/%s/%s-%s' % (author, package, version))
        response = conn.getresponse()

        if (response.status != 200):
            # maybe authors changed. Try parse HTML
            author = get_author_from_html(package, version)
            if not author:
                raise Exception("MetaCPAN - get_download_url (%s, %s) - returned %d and no author" % (package, version, response.status))

            # 3rd try with the value in HTML
            conn = httplib.HTTPConnection('api.metacpan.org')
            conn.request('GET', '/v0/release/%s/%s-%s' % (author, package, version))
            response = conn.getresponse()

            if (response.status != 200):
                raise Exception("MetaCPAN - get_download_url2 (%s, %s) - returned %d" % (package, version, response.status))

        json_data = response.read().decode('UTF-8')
        data = json.loads(json_data)

    if data.has_key('download_url'):
        return data['download_url']
    else:
        return None


def get_latest(package, last_checked=None):
    """
        Get the latest version of a package
    """
    package = _other_name(package)
    package = package.replace('::', '-')

    json_data = fetch_page('http://api.metacpan.org/v0/release/%s' % package, last_modified=last_checked)

    if json_data is None: # NB: empty string is not None but will fail the check
        return 304, 304

    data = json.loads(json_data)

    # don't process DEV/TRIAL packages
    # devel versions for some packages like Moose
    # mix up with regular versions
    if data['maturity'] != "released":
        return None, None

    version = None
    if data.has_key('version'):
        version = data['version']
    elif data.has_key('version_numified'):
        version = data['version_numified']

    released_on = get_release_date(package, version, data)

    return version, released_on

def get_url(package, version=None):
    """
        Return homepage, repo, bugtracker URLs for a package
    """
    package = _other_name(package)
    package = package.replace('::', '-')

    urls = {
            'homepage'   : 'https://metacpan.org/release/%s' % package,
            'repository' : 'https://metacpan.org/release/%s' % package,  # for metacpan SCM type
            'bugtracker' : 'https://rt.cpan.org/Public/Dist/Display.html?Name=%s' % package,
        }

    conn = httplib.HTTPConnection('api.metacpan.org')
    conn.request('GET', '/v0/release/%s' % package)
    response = conn.getresponse()

    if (response.status != 200):
        raise Exception("MetaCPAN - get_url - returned %d" % response.status)

    json_data = response.read().decode('UTF-8')
    data = json.loads(json_data)

    if data.has_key('resources'):
        resources = data['resources']

        if resources.has_key('repository') and resources['repository'].has_key('url'):
            urls['repository'] = resources['repository']['url']

        if resources.has_key('bugtracker') and resources['bugtracker'].has_key('web'):
            urls['bugtracker'] = resources['bugtracker']['web']

        if resources.has_key('homepage'):
            urls['homepage'] = resources['homepage']

    return urls

def compare_versions(ver1, ver2):
    """
        TODO:
    """
    return 0

def get_latest_from_rss():
    """
        @return - list of (name, version, released_on)
    """
    rss = fetch_page("https://metacpan.org/feed/recent?f=l") # filter=latest
    dom = parseString(rss)
    result = []
    for item in dom.getElementsByTagName("item"):
        try:
            # titles are in the form Dist-Zilla-Plugin-Test-PodSpelling-2.002005
            title_parts = item.getElementsByTagName("title")[0].firstChild.wholeText.split("-")

            version = title_parts[-1] # version is always the last component

            # skip DEV versions
#todo: better match, this is of the form MAJOR.MINOR_DEV
            if version.find('_') > -1:
                continue

            name = '::'.join(title_parts[:-1])

            pub_date = item.getElementsByTagName("dc:date")[0]
            released_on = datetime.strptime(pub_date.firstChild.wholeText, '%Y-%m-%dT%H:%M:%SZ')

            result.append((name, version, released_on))
        except:
            continue

    return result


if __name__ == "__main__":
    latest = get_latest_from_rss()
    from pprint import pprint
    pprint(latest)

    unsorted = ['0.3.2.1.1', '0.3.2.1']
    print "Unsorted:"
    for v in unsorted:
        print v

#    unsorted.sort(compare_versions)
    print "Sorted:"
    for v in unsorted:
        print v

    for name in ["GD::Graph"]:
        latest, released_on = get_latest(name)
        urls = get_url(name)
        print latest, released_on, type(released_on), urls

    for name, ver in [('YAML', '0.70'), ('Dancer', '1.3092'), ('DBI', '1.609'), ('Crypt::SSLeay', '0.57')]:
        try:
            print get_release_date(name, ver), name, ver
        except:
            pass

    print "Download URL is ", get_download_url("Crypt::SSLeay", "0.57")
    print "Download URL is ", get_download_url("Crypt::SSLeay", "0.54") # from BackPAN

