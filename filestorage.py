################################################################################
#
#   Copyright (c) 2014, Alexander Todorov <atodorov@nospam.dif.io>
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
from django.conf import settings
from django.core.files import locks
from django.core.files.storage import FileSystemStorage


class OverwriteFileSystemStorage(FileSystemStorage):
    """
        A simple class that will overwrite existing files on disk.
    """

    file_overwrite = getattr(settings, "DEFAULT_FILE_STORAGE_OVERWRITE", True)

    def get_available_name(self, name):
        """ Overwrite existing file with the same name. """
        if self.file_overwrite:
            return name
        return super(OverwriteFileSystemStorage, self).get_available_name(name)

    def _save(self, name, content):
        """ This is similar to the parent calss but removes any safe-guards against existing files """
        if not self.file_overwrite:
            return super(OverwriteFileSystemStorage, self)._save(name, content)

        full_path = self.path(name)

        # Create any intermediate directories that do not exist.
        # Note that there is a race between os.path.exists and os.makedirs:
        # if os.makedirs fails with EEXIST, the directory was created
        # concurrently, and we can continue normally. Refs #16082.
        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
        if not os.path.isdir(directory):
            raise IOError("%s exists and is not a directory." % directory)

        # This file has a file path that we can move.
        if hasattr(content, 'temporary_file_path'):
            file_move_safe(content.temporary_file_path(), full_path)
            content.close()

        # This is a normal uploadedfile that we can stream.
        else:
            flags = (os.O_WRONLY | os.O_CREAT | getattr(os, 'O_BINARY', 0))
            # The current umask value is masked out by os.open!
            fd = os.open(full_path, flags, 0o666)
            _file = None
            try:
                locks.lock(fd, locks.LOCK_EX)
                for chunk in content.chunks():
                    if _file is None:
                        mode = 'wb' if isinstance(chunk, bytes) else 'wt'
                        _file = os.fdopen(fd, mode)
                    _file.write(chunk)
            finally:
                locks.unlock(fd)
                if _file is not None:
                    _file.close()
                else:
                    os.close(fd)

        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(full_path, settings.FILE_UPLOAD_PERMISSIONS)

        return name
