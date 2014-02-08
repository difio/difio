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
from urlgrabber.grabber import URLGrabber

def download_file(url, dirname):
    """
        Download @url and save to @dirname.
        @return - filename of saved file
    """
    # pycurl is picky about Unicode URLs, see rhbz #515797
    url = url.encode('ascii', 'ignore')

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    basename = os.path.basename(url)
    filename = "%s/%s" % (dirname, basename)

    if os.path.exists(filename):
        raise Exception("File %s already exists! Not downloading!" % filename)

    g = URLGrabber(reget=None)
    local_filename = g.urlgrab(url, filename)
    return local_filename

def remove_file(filename):
    """
        Remove @filename.
    """
    os.remove(filename)


if __name__ == "__main__":
    import tar

####### GEM

    dirname = '/tmp/newdir'
    f = download_file('https://rubygems.org/gems/columnize-0.3.5.gem', dirname)
    print "Downloaded ", f

#    tar.extract_gem(f, "%s/columnize" % dirname)
#    remove_file(f)
#    print "Removed ", f

