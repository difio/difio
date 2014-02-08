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
import glob
import gzip
import shutil
import tarfile
import zipfile
from bz2 import BZ2Compressor

def _ensure_read_access(tarfileobj):
    """
From: https://gist.github.com/124597

Ensure that the given tarfile will be readable by the user after
extraction.

Some tarballs have u-x set on directories. They may as well have u-r set
on files. We reset such perms here.. so that the extracted files remain
accessible.

See also: http://bugs.python.org/issue6196
    """
    EXECUTE = 0100
    READ = 0400
    dir_perm = EXECUTE
    file_perm = EXECUTE | READ

    # WARNING: if the tarfile had a huge list of files, this could be a
    # potential performance bottleneck.
    for tarinfo in tarfileobj.getmembers():
        tarinfo.mode |= (dir_perm if tarinfo.isdir() else file_perm)

def _get_top_dir_tar(tarfileobj): # FALSE NEGATIVE
    """
        Many tarball-s contain a top-level directory with everything underneat.
        This is breaking diff so we want to extract all members without the top-level
        parent directory.

        @return - name of toplevel directory
    """
    top_lvl = []

    # grab all toplevel opjects
    for tarinfo in tarfileobj.getmembers():
        path = tarinfo.path.strip('/')
        if path.count('/') == 0:
            top_lvl.append(tarinfo)

    if (len(top_lvl) == 1) and top_lvl[0].isdir():
        return top_lvl[0].path

    return None

def _get_top_dir_zip(zipfileobj): # FALSE NEGATIVE
    """
        @return - name of toplevel directory
    """
    top_lvl = {}

    # grab all toplevel opjects
    for file in zipfileobj.namelist():
        try:
            path = file.strip('/').split('/')[0]
            top_lvl[path] = 1
        except IndexError: # top-level file with no dir
            top_lvl[path] = 1

    top_lvl = top_lvl.keys()

    if len(top_lvl) == 1:
        return top_lvl[0]

    return None

def _move_up(tarfileobj, dirname, get_top_dir_callback):
    """
        Move extracted files one level up
        and delete the top-level directory
    """
    # move files around and delete top_dir
    top_dir = get_top_dir_callback(tarfileobj)

    if top_dir and top_dir not in ['.']:
        if os.system('cp -r "%s/%s"/* "%s"' % (dirname, top_dir, dirname)) != 0:
            raise Exception("FAILED: _move_up %s, %s" % (dirname, top_dir))

        shutil.rmtree('%s/%s' % (dirname, top_dir), True)


def untar(filename, dirname): # FALSE NEGATIVE
    """
        Extract @filename into @dirname
        where @filename is a [compressed] tar archive
    """

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    # open for read, transparent compression enabled
    f = tarfile.open(name=filename, mode='r:*')
    try:
        _ensure_read_access(f)
        try:
            f.extractall(dirname)
        except: # this can fail if we have unicode file names in the archive
            pass
        _move_up(f, dirname, _get_top_dir_tar)
    finally:
        f.close()


def unzip(filename, dirname):
    """
        Extract @filename into @dirname
        where @filename is a zip archive
    """

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    # open for read, transparent compression enabled
    f = zipfile.ZipFile(filename, 'r')
    try:
        # todo: do we need to _ensure_read_access() here ???
        f.extractall(dirname)
        _move_up(f, dirname, _get_top_dir_zip)
    finally:
        f.close()

def gunzip(filename, dirname):
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    out_name = dirname + '/' + os.path.basename(filename).replace('.gz', '')

    try:
        in_file = gzip.open(filename, 'rb')
        out_file = open(out_name, 'wb')

        contents = in_file.read(1024*1024)

        while contents:
            out_file.write(contents)
            contents = in_file.read(1024*1024)

    finally:
        in_file.close()
        out_file.close()


def extract_gem(filename, dirname):
    """
        Extract @filename into @dirname
        where @filename is a Ruby .gem file
        X.gem (tar archive) contains data.tar.gz and metadata.gz
    """

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    # open for read, transparent compression enabled
    f = tarfile.open(name=filename, mode='r:*')
    try:
        # todo: _ensure_read_access()
#        f.extract("data.tar.gz", dirname)
        f.extractall(dirname)
    finally:
        f.close()

    data_tar_gz = dirname + "/data.tar.gz"
    metadata_gz = dirname + "/metadata.gz"

    try:
        gunzip(metadata_gz, dirname)
    finally:
        os.remove(metadata_gz)

    try:
        # open for read, transparent compression enabled
        f = tarfile.open(data_tar_gz, mode='r:gz', ignore_zeros=True)

        try:
            # todo: _ensure_read_access()
            f.extractall(dirname)
        finally:
            f.close()

    finally:
        os.remove(data_tar_gz)



def bz2compress(data):
    compressor = BZ2Compressor(9)
    return compressor.compress(data) + compressor.flush()


if __name__ == "__main__":
    pass
