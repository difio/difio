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

from django.conf import settings
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

