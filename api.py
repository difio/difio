# -*- coding: utf8 -*-

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


import os
import shutil
from utils import files_in_dir
from utils import get_test_dirs

import filters
from pygments import highlight
from pygments import lexers
from pygments.formatters import NullFormatter


def generate_anything_from_source(pv, dirname, contentdir, callback):
    """
        Traverse a given directory and generate extra content from it:
        API definitions, file type definitions, test case count, etc.

        @pv - PackageVersion object
        @dirname - directory of local git repo where this version is the
        *CURRENT* checkout

        @contentdir - string - where to store the generated files
        @callback - func - callback to generate content

        @return - list - results from callback(file)
    """
    results = []

    if not os.path.exists(contentdir):
        os.makedirs(contentdir)

    os.chdir(contentdir)

    # empty directory => git init
    if not os.listdir(contentdir):
        if os.system('git init') != 0:
            raise Exception("FAILED: git init in %s" % contentdir)


    #check if the same tag already exists and skip the import
    version = pv.version.replace(" ", "_")
    version = version.replace(".", "\.")
    if os.system('git tag | grep "^%s$"' % version) == 0: # tag already exists
        return [] # we have no idea if content was generated in the previous run
                    # so return []

    # remove all content files from previous tag.
    # we're doing this because tags are not imported in sequence.
    for p in os.listdir(contentdir):
        if p == ".git": # skip git directory
            continue

        if os.path.isfile(p):
            os.remove(p)

        if os.path.isdir(p):
            shutil.rmtree(p, True) # ignore errors


    os.chdir(dirname)
    # MAKE SURE we're working on the tag for this version
    if os.system('git checkout "%s"' % pv.version.replace(" ", "_")) != 0:
        raise Exception("FAILED: git checkout - tag doesn't exist")


    # walk all files and generate the content
    l = len(dirname)+1

    # create empty .gitignore so we can commit
    f = open(os.path.join(contentdir, ".gitignore"), 'w')
    f.close()

    for filename in files_in_dir(dirname):
        # skip hidden files, files in .git, .hg directories
        # .git files will also override local .git/ directory
        if filename.find('/.') > -1:
            continue

        targetfilename = os.path.join(contentdir, filename[l:]) # absolute path

        # create subdirectories
        base_dir_name = os.path.dirname(targetfilename)
        if not os.path.exists(base_dir_name):
            os.makedirs(base_dir_name)

        res = callback(filename, contentdir, targetfilename)
        if res is not None:
            results.append(res)

    # all done, now commit
    os.chdir(contentdir)
    if os.system("git add .") != 0:
        raise Exception("FAILED: git add %s/%s" % (contentdir, pv.__unicode__()))

    # this may fail if nothing has changed
    # use -a to commit removed files
    cmdline = "git commit -a -m 'Content gen %s' --author='Difio <no-reply@dif.io>'" % pv.__unicode__() # FALSE NEGATIVE
    ret_code = os.system(cmdline)
    if ret_code not in [0, 1, 256]:
        raise Exception("FAILED: git commit %s/%s - return value %d" % (contentdir, pv.__unicode__(), ret_code))

    if os.system("git tag '%s'" % pv.version.replace(" ", "_")) != 0:
        raise Exception("FAILED: git tag %s/%s" % (contentdir, pv.__unicode__()))

    # go back to the original source
    # so that other stuff doesn't break
    os.chdir(dirname)

    return results # to the caller


def api_gen_callback(filename, contentdir, targetfile):   # FALSE NEGATIVE
    """
        Generate API definition for @filename,
        storing it in @contentdir as @targetfile (absoute path)

        @return - bool - True if content was generated
    """
    # skip symlinks when generating API
    if os.path.islink(filename):
        return None

    skip_file = False
    # skip tests when generating API
    dirs_to_skip = get_test_dirs()
    dirs_to_skip.append('doc/')
    dirs_to_skip.append('docs/')
    dirs_to_skip.append('example/')
    dirs_to_skip.append('examples/')
    dirs_to_skip.append('example_project/')
    dirs_to_skip.append('migrations/') # South migrations for Python
    dirs_to_skip.append('setup.py') # Python setup file

    for test_dir in dirs_to_skip:
        if filename.find('/' + test_dir) > -1:
            return False

    api_text = get_api_from_file(filename)
    if api_text:
        print filename
        f = open(targetfile, 'w')
        f.write(api_text.encode('UTF-8', 'replace'))
        f.close()
        return True
    else:
        return False


def get_api_from_file(filename):
    """
        @filename - source file to parse and extract API symbols
        @return - string - API definition

        Extract API symbols from a source file.
    """
    lex = None

# start language definitions - sorted by lang name

    if filename.lower().endswith('.java'):
        lex = lexers.JavaLexer()
        lex.add_filter(filters.JavaAPIFilter())
    elif filename.lower().endswith('.php'):
        lex = lexers.PhpLexer(startinline=True)
        lex.add_filter(filters.PHPAPIFilter())
    elif filename.lower().endswith('.py'):
        lex = lexers.PythonLexer()
        lex.add_filter(filters.PythonAPIFilter())


# end language definitions

    if lex:
        code = open(filename, 'r').read()
        return highlight(code, lex, NullFormatter())+"\n"
    else:
        return None


