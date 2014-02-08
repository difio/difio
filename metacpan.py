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

import cpan
import json
import httplib
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def diff_tags(tag1, tag2, file = None):
    """
        Produce a diff taken from metacpan.org
        Used for packages which have not defined their
        upstream sources.

        @tag1, @tag2 - string - OWNER/distribution-version, e.g.
            SMUELLER/Parse-CPAN-Meta-1.40
            DAGOLDEN/Parse-CPAN-Meta-1.4402

        @file - string - if specified return diff only for this file
    """

    conn = httplib.HTTPConnection('api.metacpan.org')
    conn.request('GET', '/v0/diff/release/%s/%s' % (tag1, tag2))
    response = conn.getresponse()

    if (response.status != 200):
        raise Exception("MetaCPAN - diff_versions(%s, %s) - returned %d" % (tag1, tag2, response.status))

    json_data = response.read().decode('UTF8', 'replace')
    data = json.loads(json_data)

    result = u""
    for d in data['statistics']:
        if file:
            if d['source'].endswith(file) or d['target'].endswith(file):
                result += d['diff']
                break
        else:
            result += d['diff']

    result = result.encode('UTF8')
    return result


def get_tags(package, version):
    author = cpan.get_author_from_html(package, version)

    # HTML doesn't contain info for the latest package.
    # get it using the API
    if not author:
        author = cpan.get_author_from_json(package)

    return "%s/%s-%s" % (author, cpan._other_name(package).replace('::', '-'), version)


def get_files(url):
    """
        Return a list of top most files.

        @url is https://metacpan.org/release/Dist
    """
    files = []

    # get the required parts first:
    package = url.split('/')[4]
    version, released_on = cpan.get_latest(package)
    tag = get_tags(package, version) # AUTHOR/Dist-VERSION


    conn = httplib.HTTPConnection('api.metacpan.org')
    conn.request('GET', '/v0/source/%s' % tag)
    response = conn.getresponse()

    if (response.status != 200):
        raise Exception("MetaCPAN - get_files(%s) - returned %d" % (tag, response.status))

    html_data = response.read().decode('UTF8', 'replace')

    for line in html_data.split('\n'):
        if line.startswith("<tr><td class='name'><a href='"):
            files.append(line.split(">")[3].split('<')[0])

    return files


if __name__ == "__main__":
    print diff_tags('SMUELLER/Parse-CPAN-Meta-1.40', 'DAGOLDEN/Parse-CPAN-Meta-1.4402')
    print diff_tags('SMUELLER/Parse-CPAN-Meta-1.40', 'DAGOLDEN/Parse-CPAN-Meta-1.4402', 'Changes')
    print diff_tags('PMQS/IO-Compress-2.023', 'PMQS/IO-Compress-2.055', 'Changes')

    print get_tags('Parse::CPAN::Meta', '1.40')
    print get_tags('Parse::CPAN::Meta', '1.4402')
    print get_tags('Cwd', '3.33')

    print get_files('https://metacpan.org/release/Parse-CPAN-Meta')
