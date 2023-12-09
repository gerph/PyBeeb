"""
Implementation of the FS interfaces for use with the PyBeeb host interfaces.

We anchor the root at '$' and use '.' as separator.
"""

import io
import os
import stat

from .fs import FSBase, FSFileBase, FSDirectoryBase, FSFileNotFoundError, FSReadFailedError


class FSBBC(FSBase):
    dirsep = '.'
    supports_mkdir = True
    supports_delete = True
    supports_rename = True

    def __init__(self, host_root_dir):
        super(FSBBC, self).__init__()
        self.host_root_dir = host_root_dir
        try:
            self.native_uid = os.getuid()
            self.native_gids = set(os.getgroups())
        except Exception:
            # If we cannot read them, then set the uid to None to allow us to bypass checks
            self.native_uid = None
            self.native_gids = set([])

    def rootname(self):
        """
        Return the name of the root directory.
        """
        return '$'

    def get_dir(self, dirname, parent_fsdir=None):
        """
        Return a given directory for a given filesystem.
        """
        return FSDirectoryBBC(self, parent_fsdir, dirname)

    def rootinfo(self):
        """
        Return a FSFile for the root.
        """
        return FSFileBBC(self, self.rootname, parent=None,
                         fileentry=DirectoryEntryNative(self, '$', None))

    def encode_to_filesystem(self, filename):
        """
        Convert from a unicode string to something in the host filesystem.
        """

        # FIXME: Perform some conversion on the character set

        # In the filesystem a '/' is reported as a '.'
        filename = filename.replace('/', '.')

        return filename

    def decode_from_filesystem(self, filename):
        """
        Convert from a host filesystem name to a unicode string for BBC.
        """

        # FIXME: Perform some conversion on the character set

        # In the filesystem a '/' is reported as a '.'
        filename = filename.replace('.', '/')

        return filename


class FSFileBBC(FSFileBase):

    def __init__(self, fs, filename, parent=None, fileentry=None):
        super(FSFileBBC, self).__init__(fs, filename, parent)
        self.fileentry = fileentry
        self._isdir = (fileentry.objtype == 2)

    def isdir(self):
        return self._isdir

    def filetype(self):
        # Fake; we don't have filetypes on the BBC
        return 0xFFF

    def open(self, mode='rb'):
        """
        Open the file, returning an io like file handle

        @param mode:    Textual mode, like 'r', 'rb', 'w', 'wb'.
        """
        data = self.read()
        return io.BytesIO(data)

    def read(self):
        """
        Read the contents of the file.
        """
        rofilename = self.fs.encode_to_filesystem(self.filename)
        # Give a reasonable timeout here as the OS might be slow to retrieve this data.
        info = self.fs.ro.sysrq('fs-file-read', timeout=5, args=[rofilename])
        if isinstance(info, NoResponse):
            raise FSFileNotFoundError("Cannot retrieve content for file '{}': No response".format(self.filename))
        if info['error']:
            raise FSReadFailedError("Cannot retrieve content for file '{}': {}".format(self.filename, info['error']))
        return info['data']

    def size(self):
        return self.fileentry.size

    def epochtime(self):
        # Fake; we don't have time stampes on the BBC
        return 0

    def can_delete(self):
        """
        Overloadable: Check whether we can delete a given file.

        @return: True if this file is deletable.
        """
        # Check the FS itself first
        if not self.fs.can_delete():
            return False
        if not self.parent().is_writeable():
            return False

        # We should be able to delete most things.
        return True

    def do_delete(self):
        """
        Overloadable: Delete the file
        """
        rofilename = self.fs.encode_to_filesystem(self.filename)
        response = self.fs.ro.sysrq('fs-file-delete', timeout=5, args=[rofilename])
        if isinstance(response, NoResponse):
            response = 'No response'
        if response['error']:
            raise FSReadFailedError("Cannot delete '{}': {}".format(self.filename, response['error']))


class DirectoryEntryNative(object):
    default_loadaddr = 0x00000000
    default_execaddr = 0x00000000
    default_attributes = 0b00110011
    hexdigits = '0123456789abcdef'

    stat_read_mask = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    stat_write_mask = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH

    def __init__(self, fs, native_name, parent):
        self.fs = fs
        self.native_name = native_name or ''
        self.name = native_name
        self.parent = parent

        self.loadaddr = self.default_loadaddr
        self.execaddr = self.default_execaddr
        self.attributes = self.default_attributes

        if native_name != '$':
            name = self.fs.decode_from_filesystem(native_name)
            explicit_loadexec = False
            if len(name) > 18 and \
               name[-9] == ',' and name[-18] == ',' and \
               all(c in self.hexdigits for c in name[-8:]) and \
               all(c in self.hexdigits for c in name[-17:-9]):
                # 1+8+1+8 for ,llllllll,eeeeeeee
                self.loadaddr = int(name[-17:-9], 16)
                self.execaddr = int(name[-8:], 16)
                name = name[:-18]
                explicit_loadexec = True

            if not explicit_loadexec:
                # The filename wasn't using explicit load and exec.
                # Let's see if we can infer anything.
                if name.endswith('.bas'):
                    name = name[:-4]
                    self.loadaddr = 0x0E00
                    # FIXME: I have a vague recollection that the address for exec
                    #        was 8023. Or possibly 801D.
                    self.execaddr = 0x8023

                elif name.endswith('.rom'):
                    name = name[:-4]
                    self.loadaddr = 0x8000
                    self.execaddr = 0x8000

                elif len(name) > 4 and \
                   name[-4] == ',' and all(c in self.hexdigits for c in name[-3:]):
                    # Filename,xxx format
                    filetype = int(name[-3:], 16)

                    # We'll just map simple ones:
                    known = True
                    if filetype == 0xFFB:
                        # Tokenised BASIC
                        self.loadaddr = 0x0E00
                        self.execaddr = 0x0E00
                    elif filetype == (0xFFF, 0xFD1):
                        # Text or Detokenised BASIC
                        self.loadaddr = 0xFFFFFFFF
                        self.execaddr = 0xFFFFFFFF
                    else:
                        known = False

                    if known:
                        name = name[:-4]

        self.name = name
        if parent is not None:
            fullpath_native = os.path.join(parent.fullpath_native, native_name)

            try:
                st = os.stat(self.native_name)
            except OSError:
                self.objtype = 0
                self.loadaddr = 0
                self.execaddr = 0
                self.size = 0
                self.attributes = 0
            else:
                self.objtype = 1
                mode = st.st_mode
                if stat.S_ISDIR(mode):
                    self.objtype = 2
                    self.size = 0
                else:
                    self.size = st.st_size

                # Determine attributes
                self.extract_attributes(st)

        else:
            # When we don't know the filetype, we leave it set to 0
            if native_name == '$':
                # This is the root entry, so fake as a directory
                self.objtype = 2
            else:
                self.objtype = 0


    def __repr__(self):
        return "<DirectoryEntryNative(%r/%r, %i, &%08x, &%08x, %i, &%x)>" \
                    % (self.name, self.native_name,
                       self.objtype, self.loadaddr, self.execaddr, self.size, self.attributes)

    def extract_attributes(self, st):
        """
        Extract the attributes from the native file.

        @param st:      stat information for the file
        """
        mode = st.st_mode
        uid = self.fs.native_uid
        if uid is None:
            return

        # Only apply the file attributes if we have some UID determinable
        rval = mode & self.stat_read_mask
        if rval == self.stat_read_mask:
            # Definitely readable
            self.attributes |= 0x11
        elif rval == 0:
            # Definitely not readable
            self.attributes &= ~0x11
        else:
            # Determine from UID/GID
            self.attributes &= ~0x11
            #print("R name=%s   uid=%i/%i  mode=%o" % (self.name, st.st_uid, uid, mode))
            if st.st_uid == uid:
                # We are the user, so check permissions for USR
                if mode & stat.S_IRUSR:
                    self.attributes |= 0x1
                if mode & stat.S_IRGRP or mode & stat.S_IROTH:
                    self.attributes |= 0x10

            elif st.st_gid in self.fs.native_gids:
                # We are in the group, so check permissions for GRP
                if mode & stat.S_IRGRP:
                    self.attributes |= 0x1
                if mode & stat.S_IROTH:
                    self.attributes |= 0x10

            else:
                if mode & stat.S_IROTH:
                    self.attributes |= 0x11

        rval = mode & self.stat_write_mask
        if rval == self.stat_write_mask:
            # Definitely writable
            self.attributes |= 0x22
        elif rval == 0:
            # Definitely not writable
            self.attributes &= ~0x22
        else:
            # Determine from UID/GID
            #print("W name=%s   uid=%i/%i  mode=%o" % (self.name, st.st_uid, uid, mode))
            self.attributes &= ~0x22
            if st.st_uid == uid:
                # We are the user, so check permissions for USR
                if mode & stat.S_IWUSR:
                    self.attributes |= 0x2
                if mode & stat.S_IWGRP or mode & stat.S_IWOTH:
                    self.attributes |= 0x20

            elif st.st_gid in self.fs.native_gids:
                # We are in the group, so check permissions for GRP
                if mode & stat.S_IWGRP:
                    self.attributes |= 0x2
                if mode & stat.S_IWOTH:
                    self.attributes |= 0x20

            else:
                if mode & stat.S_IWOTH:
                    self.attributes |= 0x22


class FSDirectoryBBC(FSDirectoryBase):
    """
    Object for retrieving information about files within a filesystem.
    """

    def __init__(self, fs, parent, dirname):
        super(FSDirectoryBBC, self).__init__(fs, parent, dirname)
        if '.' in dirname:
            _, leaf = dirname.rsplit('.', 1)
        else:
            leaf = dirname
        self.native_name = self.fs.encode_to_filesystem(leaf)
        self._bbcfiles = None

    @property
    def fullpath_native(self):
        if self.dirname == '$':
            return self.fs.host_root_dir
        if self.parent is not self and self.parent:
            return os.path.join(self.parent.fullpath_native, self.native_name)
        return os.path.join(self.fs.host_root_dir, self.native_name)

    def get_file(self, fileref):
        """
        Overridden: Return a FSFile object for this file.
        """
        return FSFileBBC(self.fs, self.fs.join(self.dirname, fileref.name), fileentry=fileref)

    def cache_files(self):
        if self._bbcfiles is None:
            filenames = os.listdir(self.fullpath_native)

            files = {}
            for filename in filenames:
                dirent = DirectoryEntryNative(fs=self.fs, native_name=filename, parent=self)
                files[dirent.name.lower()] = dirent
            self._bbcfiles = files
        return self._bbcfiles

    def uncache_files(self):
        self._bbcfiles = None

    def lookup_dirent(self, leafname):
        files = self.cache_files()
        dirent = files.get(leafname.lower(), None)
        if not dirent:
            raise FSFileNotFoundError("File '{}.{}' not found", self.dirname, leafname)
        return dirent

    def lookup_fullpath_native(self, leafname):
        dirent = self.lookup_leafname(leafname)
        host_filename = os.path.join(self.fullpath_native, dirent.native_name)
        return host_filename

    def get_filelist(self):
        """
        Overridden: Return a list of the files in this directory.

        @return: A list of objects which describe the files in the directory; can be
                 leafnames as strings or structures. The values will be passed to
                 get_file() to convert to a FSFile object.
        """
        files = self.cache_files()
        return files.values()

    def is_writeable(self):
        """
        Overloadable: Check whether we can write to this directory.

        @return: True if the files in this folder are modifyable, False if we not.
        """
        # FIXME: Make this configurable
        return True

    def do_mkdir(self, leafname):
        """
        Overloadable: Create a directory with a given name.

        @param leafname: leafname of the directory to create.
        """
        filename = self.fs.join(self.dirname, leafname)
        host_leafname = self.fs.encode_to_filesystem(leafname)
        host_filename = os.path.join(self.fullpath_native, host_leafname)
        self.uncache_files()
        try:
            os.mkdir(host_filename)
        except Exception as exc:
            raise FSReadFailedError("Cannot create directory '{}': {}".format(filename, exc))

    def do_rename(self, source_leafname, dest_leafname):
        """
        Overloadable: Rename a given file within the directory

        @param source_leafname: leafname to rename from
        @param dest_leafname:   leafname to rename as
        """
        source_filename = self.fs.join(self.dirname, source_leafname)
        dest_filename = self.fs.join(self.dirname, dest_leafname)

        source_host_filename = self.lookup_fullpath(source_leafname)

        dest_host_leafname = self.fs.encode_to_filesystem(leafname)
        dest_host_filename = os.path.join(self.fullpath_native, dest_host_leafname)

        try:
            os.rename(source_filename, dest_filename)
        except Exception as exc:
            # FIXME: We could be more specific here
            raise FSReadFailedError("Cannot create rename '{}' to '{}': {}".format(source_filename, dest_filename,
                                                                                   exc))
