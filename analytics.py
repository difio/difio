#!/usr/bin/env python

################################################################################
#
#   Copyright (c) 2013-2014, Alexander Todorov <atodorov@nospam.dif.io>
#
#   Untilities to generate additional information about version updates.
#
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
import utils
import magic
import subprocess
from models import *
from django.template.defaultfilters import filesizeformat

SCM_DIFF_ALL_CMD[utils.SCM_APIGEN]

INFO="INFO"
PASS="PASS"
VERIFY="VERIFY"
FAIL="FAIL"

def api_diff(apidir, api_version_old, api_version_new):
    """
        Generate API diff text

        @return - tuple - (SEVERITY, TEXT)
    """
    severity = INFO
    cmdline = SCM_DIFF_ALL_CMD[utils.SCM_APIGEN] % (api_version_old, api_version_new)

    proc = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=apidir)
    api_diff = proc.communicate()[0]

    if (api_diff == "") and (proc.returncode == 0):
        api_diff = utils.INFO_NO_API_DIFF_FOUND
        severity = PASS

    api_diff = api_diff.decode('UTF8', 'replace')

    return (severity, api_diff)


def full_diff(pkg_scm_type, dirname, version_old, version_new, subpackage_path):
    """
        Generate full diff text
    """
    cmdline = None
    diff = utils.INFO_NOT_AVAILABLE
    # NB: diffing a subpath is the same as diffing changelog only!
    if subpackage_path and SCM_DIFF_CHANGELOG_CMD[pkg_scm_type]:
        cmdline = SCM_DIFF_CHANGELOG_CMD[pkg_scm_type] % (version_old, version_new, subpackage_path)
    elif SCM_DIFF_ALL_CMD[pkg_scm_type]:
        cmdline = SCM_DIFF_ALL_CMD[pkg_scm_type] % (version_old, version_new)

    if cmdline:
        proc = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=dirname)
        diff = proc.communicate()[0]
# decode after bzipping in the caller
#        diff = diff.decode('UTF8', 'replace')

    return (INFO, diff)


def diff_stats(scm_type, cwd, old_ver, new_ver, only_last_line, subpackage_path=None):
    """
        Returns something like:
        3 files changed, 5 insertions, 2 deletions

        @scm_type - int - type of SCM - determines which command is used
        @cwd - string - current working directory - usualy a git clone
        @old_ver - string - old version tag/commit
        @new_ver - string - new version tag/commit
        @only_last_line - bool - if True only the short status message is returned
    """
    if SCM_DIFF_STAT_CMD[scm_type] is None:
        return (INFO, utils.INFO_NOT_AVAILABLE)

    cmdline = SCM_DIFF_STAT_CMD[scm_type] % (old_ver, new_ver)
    if subpackage_path:
        cmdline += " -- %s" % subpackage_path

    proc = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)
    text = proc.communicate()[0]
    text = text.decode('UTF8', 'replace').strip('\n') # keep leading white space for changed files list
    if not text:
        text = utils.INFO_NOT_AVAILABLE

    # take the last line only to avoid using pipes in subprocess.Popen
    # text is stripped of new lines above so no empty list elements at the end
    if only_last_line:
        for l in text.split("\n"):
            text = l.strip() # keep leading white space for changed files list

    return (INFO, text)

def package_size_change(advisory):
    """
        Return size change as text

        @advisory - Advisory object
    """
    severity = PASS
    if advisory.severity == utils.SEVERITY_MEDIUM:
        severity = VERIFY

    if advisory.severity == utils.SEVERITY_HIGH:
        severity = FAIL

    return (severity, "%s &raquo;&raquo; %s" % (filesizeformat(advisory.old.size), filesizeformat(advisory.new.size)))


def list_modified_files(cwd, old_ver, new_ver):
    """
NB: Uses Git and the tarball/ directory

        Returns the list of changed files with insert delete stats:
         js/jquery/resources/jquery.min.js         |    9 +-
         setup.py                                  |   12 +-

        Severity - INFO if only tests have changed, VERIFY otherwise
    """

    (severity, files_list) = diff_stats(utils.SCM_GIT, cwd, old_ver, new_ver, False)
    files_list = files_list.split('\n')[:-1] # skip the last line, this is the summary

    changed_test_count = 0
    for f in files_list:
        for test_dir in utils.get_test_dirs():
            # if file name doesn't match a common test case pattern
            if f.lower().find(test_dir) > -1:
                changed_test_count += 1
                break # break from the inner loop, this filename already matches test case

    if changed_test_count == len(files_list):
        severity = INFO # only tests have changed
    else:
        severity = VERIFY

    if files_list:
        return (severity, "\n".join(files_list))
    else:
        return (PASS, 'None')

def get_file_list_changes(cwd, old_ver, new_ver):
    """
NB: Uses Git and the tarball/ directory

        Returns a list of added, deleted, renamed and chmod files.
        The data is then filtered through other test cases

    """
    cmdline = "git diff -M --summary %s..%s" % (old_ver, new_ver)
    proc = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)
    text = proc.communicate()[0]
    text = text.decode('UTF8', 'replace').strip('\n') # keep leading white space for changed files list
    if not text:
        return (FAIL, utils.INFO_NOT_AVAILABLE)

    return (INFO, text)

def filter_added_files(file_list):
    """
        @file_list - string - output of git diff --summary

SEVERITY - INFO - added files are usually new functionality or tests or resources
    """
    files = []
    for f in file_list.split('\n'):
        if f.find('create mode') > -1:
            files.append(f)

    if files:
        return (INFO, "\n".join(files))
    else:
        return (PASS, "None")

def filter_removed_files(file_list):
    """
        @file_list - string - output of git diff -M --summary

SEVERITY- FAIL - removing modules/files can break the API
    """
    files = []
    for f in file_list.split('\n'):
        if f.find('delete mode') > -1:
            files.append(f)

    if files:
        return (FAIL, "\n".join(files))
    else:
        return (PASS, "None") 

def filter_renamed_files(file_list):
    """
        @file_list - string - output of git diff -M --summary

SEVERITY- FAIL - renaming modules/files can break the API
    """
    files = []
    for f in file_list.split('\n'):
        if f.find('rename') > -1:
            files.append(f)

    if files:
        return (FAIL, "\n".join(files))
    else:
        return (PASS, "None")

def filter_permission_change(file_list):
    """
        @file_list - string - output of git diff -M --summary

SEVERITY- FAIL - permission changes are bad, usually security thing
but there are valid use-cases too. Just verify manually.
    """
    files = []
    for f in file_list.split('\n'):
        if f.find('mode change') > -1:
            files.append(f)

    if files:
        return (FAIL, "\n".join(files))
    else:
        return (PASS, "None")


def symlinks_test(dirname):
    """
Traverse the directory and report any symlinks found.
Generally packages should not distribute symlinks.

Severity - FAIL if links found, PASS otherwise
    """

    links = []

    for (path, dirs, files) in os.walk(dirname):
        if path.find('/.git') > -1:
            continue

        # search for directory links
        for d in dirs:
            dname = os.path.join(path, d)
            if os.path.islink(dname):
                links.append(os.path.relpath(dname, dirname)+'/')

        # search for file links
        for f in files:
            fname = os.path.join(path, f)
            if os.path.islink(fname):
                links.append(os.path.relpath(fname, dirname))

    if links:
        return (FAIL, '\n'.join(links))
    else:
        return (PASS, "None")

def file_types_diff(cwd, old_ver, new_ver):
    """
NB: Uses Git and the magic/ directory

Select only files that are Copied (C), Modified (M), Renamed (R),
have their type (i.e. regular file, symlink, submodule, ...) changed (T)

        Returns a list of changed file types!
    """
    # diff only Modified and Type changed
    cmdline = "git diff -M --diff-filter=MT %s..%s" % (old_ver, new_ver)
    proc = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)
    text = proc.communicate()[0]
    text = text.decode('UTF8', 'replace').strip('\n') # keep leading white space

    if text:
        return (FAIL, text)
    else:
        return (PASS, "None")


def virus_scan(cwd):
    """
        Perform virus scan using ClamAV.

        @return  - ClamAV output
    """
    # print only infected files, recursive scan, skip .git/ directory
    cmdline = "/usr/bin/clamscan -i -r --exclude-dir=.git ." # NB: dot at the end prints relative file names
    proc = subprocess.Popen(cmdline.split(' '), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)
    text = proc.communicate()[0]
    text = text.decode('UTF8', 'replace').strip()
    if not text:
        return (FAIL, utils.INFO_NOT_AVAILABLE)

    return (VERIFY, text)

def parse_virus_scan(text):
    """
        Parse ClamAV output
    """

    for line in text.split('\n'):
        if line.find('Infected files:') > -1:
            if line.replace('Infected files:', '').strip() == '0':
                return (PASS, line + '\n\n' + text) # return all lines
            else:
                return (FAIL, line + '\n\n' + text) # return all lines

def test_case_count_callback(filename, contentdir, targetfile):   # FALSE NEGATIVE
    """
        Generate API definition for @filename,
        storing it in @contentdir as @targetfile (absolute path)

        @return - bool - True if content was generated
    """
    if os.path.islink(filename):
        return None

    fname = filename.lower()
    for test_dir in utils.get_test_dirs():
        if fname.startswith(test_dir) or (fname.find('/'+test_dir) > -1):
            return os.path.relpath(targetfile, contentdir)

def test_case_count_change(old_tests, new_tests):
    """
        If new tests are less then FAIL and report
        the names of deleted tests.

        @old_tests, @new_tests - lists of relative file names
    """
    # first sanitize the input. Some elements may be None so remove them
    old_tests = [t for t in old_tests if t]
    new_tests = [t for t in new_tests if t]

    old_count = len(old_tests)
    new_count = len(new_tests)

    if new_count > old_count:
        return (PASS, "%d &raquo;&raquo; %d" % (old_count, new_count))
    elif new_count == old_count:
        if (new_count == 0):
            return (FAIL, "This package doesn't ship any tests")
        else:
            return (VERIFY, "No tests were added in this release")
    else: # new < old
        removed = ["%d &raquo;&raquo; %d" % (old_count, new_count)]
        for test in old_tests:
            if test not in new_tests: # NB: this ignores renamed tests
                removed.append("Removed test case: %s" % test)
        return (FAIL, "\n".join(removed))


def file_size_callback(filename, contentdir, targetfile):  # FALSE NEGATIVE
    """
        Return {fname: size}
    """
    if os.path.islink(filename):
        return None

    stat = os.lstat(filename)
    return {os.path.relpath(targetfile, contentdir) : stat.st_size}

def normalize_list_of_dict_into_dict(alist):
    """
        Info is generated as a list of dict
        objects with a single key. 

        @alist - the list in question.
        @return - normalized dict with multiple keys
    """

    result = {}
    for element in alist:
        for key in element.keys():
            result[key] = element[key]

    return result


def file_size_changes(sizes_old, sizes_new):
    """
        Inform on any files which are present in both
        versions and:

        * were 0 bytes and became non-zero;
        * were non-zero sized and became 0 bytes;
        * size changed over 20% and 20KB
    """
    results = []
    old_file_names = sizes_old.keys()

    for file_name in sizes_new.keys():
        if file_name in old_file_names: # present in both versions
            old_size = sizes_old[file_name]
            new_size = sizes_new[file_name]

            # keep this before text conversion to speed-up things
            if old_size == new_size:
                continue

            # convert sizes to human readable format
            old_size_text = filesizeformat(old_size)
            new_size_text = filesizeformat(new_size)

            # zero/non-zero changes
            if ((old_size == 0) and (new_size > 0)) or \
                ((old_size > 0) and (new_size == 0)):
                results.append("Zero vs non-zero change: %s from %s to %s" % (file_name, old_size_text, new_size_text))
            else: # neither one is zero
                delta = abs(new_size - old_size)
                percent = int(delta*100/old_size)

                # > 20KB and > 20%
                if (delta > 20*1024*1024) and (percent >= 20):
                    results.append("Too big change: %s from %s to %s" % (file_name, old_size_text, new_size_text))

    if results:
        return (FAIL, "\n".join(results))
    else:
        return (PASS, "Suspicious changes: 0")


def filetype_gen_callback(filename, contentdir, targetfile):  # FALSE NEGATIVE
    """
        Generate file type definition for @filename,
        storing it in @contentdir as @targetfile (absoute path)
    """
    if os.path.islink(filename):
        return None

    # generate file type using python magic
    file_type = magic.from_file(filename)
    f = open(targetfile, 'w')
    f.write(file_type.encode('UTF-8', 'replace'))
    f.write("\n") # always include new line to avoid git complaining
    f.close()

    return {os.path.relpath(targetfile, contentdir) : file_type}


def added_non_text_files(types_old, types_new):
    """
        Inform on newly added files which are not text.
    """
    results = []
    old_names = types_old.keys()

    for file_name in types_new.keys():
        # skip some metadata files
        do_skip = False
        for skip_me in ["checksums.yaml.gz", "checksums.yaml.gz.sig", "metadata.gz.sig", "data.tar.gz.sig"]:
            if file_name.endswith(skip_me):
                do_skip = True
                break
        if do_skip:
            continue

        if file_name in old_names: # skip binaries from old version
            continue

        # inspect only new files
        new_type = types_new[file_name]

        if new_type.find("text") > -1: # skip text files
            continue

        results.append("%s : %s" % (file_name, new_type))

    if results:
        return (FAIL, "\n".join(results))
    else:
        return (PASS, "None")
