################################################################################
#
#   Copyright (c) 2013-2014, Alexander Todorov <atodorov@nospam.dif.io>
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


import string
from django.contrib import messages
from models import PHP_PEAR_PKG, PHP_PEAR2_PKG

def parse_pip_freeze(request, package_text):   # FALSE NEGATIVE
    """
        Parse the output of `pip freeze'.

        @request - HttpRequest object - used for showing error messages
        @package_text - string - the output of the command

        @return - dict - { 'errors' : int, 'packages' : [{ 'n' : 'v' }]}
    """
    result = {'packages' : []}
    errors = 0
    for line in package_text.split("\n"):
        # this will cause comments and blanks to be skipped
        # also fix the case where comment is after the package version
        # e.g. six==1.3 # Fix conflict
        pkg_ver = line.split('#')[0]

        pkg_ver = pkg_ver.strip()

        # skip empty lines
        if not pkg_ver:
            continue

        # try to find warnings
        if pkg_ver.find('Warning:') > -1:
            messages.warning(request, pkg_ver)
            errors += 1

        try:
            (name, version) = pkg_ver.split('==')
            # a fix for package list that came out from some Linux distro
            # not a virtual env
            if name.startswith('python-'):
                name = name.replace('python-', '')
        except:
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)
            continue

        if (not name) or (not version):
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)

        result['packages'].append({'n' : name, 'v' : version})

    result['errors'] = errors

    return result


def parse_bundle_list(request, package_text):   # FALSE NEGATIVE
    """
        Parse the output of `bundle list` or `gem list`.

        @request - HttpRequest object - used for showing error messages
        @package_text - string - the output of the command

        @return - dict - { 'errors' : int, 'packages' : [{ 'n' : 'v' }]}
    """
    result = {'packages' : []}
    errors = 0
    for line in package_text.split("\n"):
        pkg_ver = line.strip()

        # skip empty lines
        if not pkg_ver:
            continue

        # skip, comes from bundle list
        if pkg_ver.startswith('Gems included by the bundle:'):
            continue

        # skip, comes from gem list
        if pkg_ver.startswith('*** LOCAL GEMS ***'):
            continue

        #  * rack-protection (1.2.0) - bundle list prefixes with space and a star
        #   journey (1.0.4) - gem list doesn't add any prefix
        if pkg_ver.startswith('* '):
            pkg_ver = pkg_ver[2:]

        try:
            (name, version) = pkg_ver.split('(')
            name = name.strip()    # strip trailing spaces
            version = version[:-1] # strip trailing )

            # because gem list may show multiple versions. add all of them
            # sass (3.1.20, 3.1.18, 3.1.5)
            # sinatra (1.3.3, 1.3.2, 1.2.6)
            # stringex (1.4.0, 1.3.0)
            for v in version.split(','):
                v = v.strip()
                if (not name) or (not v):
                    errors += 1
                    messages.error(request, "'%s' is not a valid input!" % pkg_ver)
                else:
                    result['packages'].append({'n' : name, 'v' : v})

        except:
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)
            continue

    result['errors'] = errors

    return result

def parse_npm_ls(request, package_text):   # FALSE NEGATIVE
    """
        Parse the output of `npm ls'.

        @request - HttpRequest object - used for showing error messages
        @package_text - string - the output of the command

        @return - dict - { 'errors' : int, 'packages' : [{ 'n' : 'v' }]}
    """
    result = {'packages' : []}
    errors = 0
    for line in package_text.split("\n"):
        pkg_ver = line.strip()

        # skip empty lines
        if not pkg_ver:
            continue

        # skip comments
        if pkg_ver.startswith('#'):
            continue

        # try to find warnings
        if pkg_ver.find('WARN') > -1:
            messages.warning(request, pkg_ver)
            errors += 1

        if pkg_ver.find('UNMET DEPENDENCY') > -1:
            messages.warning(request, pkg_ver)
            errors += 1

        # skip lines which are not packages
        if pkg_ver.find('@') == -1:
            continue

        # remove non ASCII characters since `npm ls` will give us
        # a tree like structure.
        pkg_ver = filter(lambda x: x in string.printable, pkg_ver)

        # remove any spaces left
        pkg_ver = pkg_ver.strip()

        try:
            (name, version) = pkg_ver.split('@')

            # For example:
            # ep_etherpad-lite@1.0.0 -> /home/repos/git/etherpad-lite/src
            # this is the application itself, so skip it.
            if version.find(' ') > -1:
                continue
        except:
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)
            continue

        if (not name) or (not version):
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)

        result['packages'].append({'n' : name, 'v' : version})

    result['errors'] = errors

    return result

def parse_perllocal(request, package_text):   # FALSE NEGATIVE
    """
        Parse perllocal.pod.

        @request - HttpRequest object - used for showing error messages
        @package_text - string - the output of the command

        @return - dict - { 'errors' : int, 'packages' : [{ 'n' : 'v' }]}
    """
    result = {'packages' : []}
    errors = 0
    name = None
    version = None

    # NB: this will only handle \n line endings. We may have problems with Perl on Windows/Mac
    # see https://docs.djangoproject.com/en/dev/topics/http/file-uploads/#uploadedfile-objects
    for line in package_text.split("\n"):
        pkg_ver = line.strip()

        # skip empty lines
        if not pkg_ver:
            continue

        # try parse name first, then version
        try:
            if pkg_ver.find('L<') > -1:
                # =head2 Tue Jul  3 17:41:12 2012: C<Module> L<CPAN::DistnameInfo|CPAN::DistnameInfo>
                name = pkg_ver.split('L<')[1].replace('>', '')
                name = name.split('|')[0]
                continue

            if pkg_ver.find('C<VERSION:') > -1:
                # C<VERSION: 0.23>
                version = pkg_ver.split(':')[1].replace('>', '').strip()

        except:
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)
            continue

        if name and version:
            result['packages'].append({'n' : name, 'v' : version})
            # reset variable since perllocal.pod is parsed in a stream fashion
            name = None
            version = None

    result['errors'] = errors

    return result

def parse_mvn_dependency_list(request, package_text):   # FALSE NEGATIVE
    """
        Parse the output of `mvn dependency:list`.

        @request - HttpRequest object - used for showing error messages
        @package_text - string - the output of the command

        @return - dict - { 'errors' : int, 'packages' : [{ 'n' : 'v' }]}
    """
    result = {'packages' : []}
    errors = 0
    for line in package_text.split("\n"):
        pkg_ver = line.strip()

        # skip empty lines
        if not pkg_ver:
            continue

        # skip lines which don't follow the format
        # [INFO] The following files have been resolved:
        # [INFO]    antlr:antlr:jar:2.7.7:provided
        # [INFO]    aopalliance:aopalliance:jar:1.0:compile
        # [INFO]    cglib:cglib-nodep:jar:2.2:test
        if pkg_ver.find('[INFO]    ') == -1:
            continue

        try:
            pkg_ver = pkg_ver[10:]
            (gid, aid, atype, version, scope) = pkg_ver.split(':')
            name = "%s:%s" % (gid, aid)
        except:
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)
            continue

        if (not name) or (not version):
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)

        result['packages'].append({'n' : name, 'v' : version})

    result['errors'] = errors

    return result


def parse_composer_show(request, package_text):   # FALSE NEGATIVE
    """
        Parse the output of `composer.phar show --installed`.

        @request - HttpRequest object - used for showing error messages
        @package_text - string - the output of the command

        @return - dict - { 'errors' : int, 'packages' : [{ 'n' : 'v' }]}
    """
    result = {'packages' : []}
    errors = 0
    for line in package_text.split("\n"):
        name = None
        version = None

        pkg_ver = line.strip()

        # skip empty lines
        if not pkg_ver:
            continue

        # skip lines w/o / - names are :vendor/:package
        if pkg_ver.find('/') == -1:
            continue

        try:
            splt = pkg_ver.split(' ')
            name = splt[0]

            # handle external PEAR repos
            if name.startswith('pear-pear.php.net'):
                name = name.split('/')[1]
                type = PHP_PEAR_PKG
            elif name.startswith('pear-pear2.php.net'):
                name = name.split('/')[1]
                type = PHP_PEAR2_PKG
            else:
                type = None

            # take the rest, strip leading space, split again
            # version is now the first component
            version = " ".join(splt[1:]).strip().split(' ')[0]
        except:
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)
            continue

        if (not name) or (not version):
            errors += 1
            messages.error(request, "'%s' is not a valid input!" % pkg_ver)

        if type:
            result['packages'].append({'n' : name, 'v' : version, 't' : type})
        else:
            result['packages'].append({'n' : name, 'v' : version})

    result['errors'] = errors

    return result

