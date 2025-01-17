"""
Interfaces to the host filesystem.
"""

import errno
import os
import stat

from .base import BBCError

open_in = 0x40
open_out = 0x80
open_up = 0xC0
open_mask = 0xC0


class BBCFileNotFoundError(BBCError):
    pass


class BBCDirNotFoundError(BBCFileNotFoundError):
    pass


class BBCNoHandlesError(BBCError):
    pass


class BBCBadHandleError(BBCError):
    pass


class DirectoryEntry(object):
    default_loadaddr = 0x00000000
    default_execaddr = 0x00000000
    default_attributes = 0b00110011
    hexdigits = b'0123456789abcdef'

    stat_read_mask = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    stat_write_mask = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH

    def __init__(self, fs, native_name, parent):
        self.fs = fs
        self.native_name = native_name or ''
        self.parent = parent

        self.loadaddr = self.default_loadaddr
        self.execaddr = self.default_execaddr
        self.attributes = self.default_attributes

        if native_name != '$':
            name = self.fs.decode_from_filesystem(native_name)
            explicit_loadexec = False
            if len(name) > 18 and \
               name[-9:-8] == b',' and name[-18:-17] == b',' and \
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
                ext = None
                #print("Checking name %r" % (name,))
                if len(name) > 4 and \
                   name[-4:-3] == b',' and all(c in self.hexdigits for c in name[-3:]):
                    ext = name[-4:]

                elif len(name) > 4 and \
                   name[-4:-3] == b'/':
                    # The name has already been decoded from the filesystem, so . => /.
                    ext = b'.' + name[-3:]

                if ext:
                    loadexec = self.fs.loadexec_from_extension.get(ext, None)
                    #print("Lookup for %r: extension %r gave %r" % (self.native_name, ext, loadexec))
                    if loadexec:
                        (self.loadaddr, self.execaddr) = loadexec
                        name = name[:-len(ext)]

        self.name = name
        self.fullpath_native = None
        self.fullpath = self.fs.join(parent.fullpath, self.name)
        if parent is not None:
            self.fullpath_native = os.path.join(parent.fullpath_native, native_name)

            try:
                st = os.stat(self.fullpath_native)
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
            if native_name == b'$':
                # This is the root entry, so fake as a directory
                self.objtype = 2
            else:
                self.objtype = 0

    def __repr__(self):
        return "<DirectoryEntry(%r/%r, %i, &%08x, &%08x, %i, &%x)>" \
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

    def generate_native_filename(self, name=None, loadaddr=None, execaddr=None):
        """
        Work out what the native filename should be for this file if the name
        or the load/exec changed
        """
        if not name:
            name = self.name
        if loadaddr is None:
            loadaddr = self.loadaddr
        if execaddr is None:
            execaddr = self.execaddr

        new_name = self.fs.generate_native_filename(name, loadaddr, execaddr, self.objtype)

        return new_name


class Directory(object):

    def __init__(self, fs, name, parent):
        self.fs = fs
        self.name = name
        #print("Creating directory %s, parent %r" % (name, parent))
        if parent:
            self.fullpath = self.fs.join(parent.fullpath, name)
        else:
            self.fullpath = self.fs.join(b'$', name)

        if parent:
            self.fullpath_native = os.path.join(parent.fullpath_native, name.decode('latin-1'))
        else:
            self.fullpath_native = self.fs.basedir
        self._files = None

    def __repr__(self):
        if self._files:
            files = "files=%s" % (len(self._files),)
        else:
            files = "files uncached"
        return "<{}(name={!r}, native={!r}, {}>".format(self.__class__.__name__,
                                                                self.fullpath,
                                                                self.fullpath_native,
                                                                files)

    @property
    def files(self):
        if not self._files:
            try:
                filenames = os.listdir(self.fullpath_native)
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    # FIXME: Find the error number
                  raise BBCFileNotFoundError(0, b"File '%s' not found" % (self.name,))
                if exc.errno == errno.ENOTDIR:
                    # FIXME: Find the error number
                  raise BBCDirNotFoundError(0, b"Directory '%s' not found" % (self.name,))
                raise

            files = {}
            #print("Files in %r (%r)" % (self.fullpath, self.fullpath_native))
            for filename in filenames:
                dirent = DirectoryEntry(fs=self.fs, native_name=filename, parent=self)
                files[dirent.name.lower()] = dirent
                #print("  %r" % (dirent,))
            self._files = files
        return self._files

    def invalidate(self):
        self._files = None

    def __getitem__(self, name):
        """
        Find a file in this directory.
        """
        dirent = self.files.get(name.lower(), None)
        if dirent is None:
            # FIXME: Find the error number
            raise BBCFileNotFoundError(0, b"File '%s' not found" % (name,))
        return dirent


class OpenFile(object):
    howmap = {
            open_in: 'rb',
            open_out: 'wb',
            open_up: 'w+b',
        }

    def __init__(self, fs, dirent, how):
        self.fs = fs
        self.handle = 0
        self.dirent = dirent
        self.how = how & open_mask
        self.openhow = self.howmap[self.how]

        #print("OpenFile(dirent=%r, how=%r): openhow=%r" % (dirent, how, self.openhow))
        self.fh = open(dirent.fullpath_native, self.openhow)

    def __repr__(self):
        return "<{}(how={})>".format(self.__class__.__name__, self.openhow)

    def close(self):
        self.fh.close()
        self.fh = None

    def ptr(self, ptr=None):
        if ptr is None:
            return self.fh.tell()
        self.fh.seek(ptr, os.SEEK_SET)

    def ext(self):
        ptr = self.ptr()
        self.fh.seek(ptr, os.SEEK_END)
        ext = self.ptr()
        self.ptr(ptr)
        return ext

    def read(self, size):
        data = self.fh.read(size)
        return data

    def write(self, data):
        self.fh.write(data)

    def flush(self):
        self.fh.flush()

    def eof(self):
        ptr = self.ptr()
        self.fh.seek(ptr, os.SEEK_END)
        ext = self.ptr()
        self.ptr(ptr)
        return ptr == ext


class FS(object):
    """
    An interface for accessing the filesystem.
    """
    loadexec_to_extension = {
            (None, 0xFFFF8023): b'.bas',
            (None, 0xFFFF801F): b'.bas',
            (0xFFFF8000, 0xFFFF8000): b'.rom',
            (0xFFFFFFFF, 0xFFFFFFFF): b'.txt',
        }
    loadexec_from_extension = {
            b'.bas': (0xFFFF0E00, 0xFFFF8023),
            b'.rom': (0xFFFF8000, 0xFFFF8000),
            b'.txt': (0xFFFFFFFF, 0xFFFFFFFF),

            # NFS style RISC OS extensions
            b',ffb': (0xFFFF0E00, 0xFFFF8023),   # Tokenised BBC BASIC
            b',fd1': (0xFFFFFFFF, 0xFFFFFFFF),   # Detokenised BBC BASIC
            b',fff': (0xFFFFFFFF, 0xFFFFFFFF),   # Text
            b'.bbc': (0xFFFF8000, 0xFFFF8000),   # BBC ROM
        }

    open_loadaddr = 0xFFFFFFFF
    open_execaddr = 0xFFFFFFFF
    filehandle_max = 255

    def __init__(self, basedir="."):
        self.basedir = basedir
        self.cached = {}
        self.filehandles = {}
        self._next_filehandle = self.filehandle_max
        self._cwd = b'$'

        try:
            self.native_uid = os.getuid()
            self.native_gids = set(os.getgroups())
        except Exception:
            # If we cannot read them, then set the uid to None to allow us to bypass checks
            self.native_uid = None
            self.native_gids = set([])

    def encode_to_filesystem(self, filename):
        """
        Convert from a unicode string to something in the host filesystem.

        @param filename:    BBC filename (latin-1)

        @return:            Filesystem filename (unicode)
        """

        # In the filesystem a '/' is reported as a '.'
        filename = filename.replace(b'/', b'.')

        # Convert the filename into unicode format
        filename = filename.decode('latin-1')

        return filename

    def decode_from_filesystem(self, filename):
        """
        Convert from a host filesystem name to a unicode string for BBC.

        @param filename:    Filesystem filename (unicode)

        @return:            BBC filename (latin-1)
        """

        # Convert the filename into encoded format
        filename = filename.encode('latin-1')

        # In the filesystem a '/' is reported as a '.'
        filename = filename.replace(b'.', b'/')

        return filename

    def join(self, *paths):
        parts = [b'$']
        for path in paths:
            if path is None or path == b'$':
                parts = [b'$']
            else:
                parts.append(path)
        if b'^' in parts:
            # Only go through the process of reconciling '^' if one was present
            return self.canonicalise(b'.'.join(parts))
        return b'.'.join(parts)

    def generate_native_filename(self, name, loadaddr, execaddr, objtype):
        """
        Work out what the native filename should be for this file if the name
        or the load/exec changed
        """

        if objtype != 2:
            # Certain load/exec extensions are able to be converted through the mapping
            ext = self.loadexec_to_extension.get((loadaddr, execaddr), None)
            if not ext:
                ext = self.loadexec_to_extension.get((loadaddr, None), None)
                if not ext:
                    ext = self.loadexec_to_extension.get((None, execaddr), None)
            if ext:
                #print("ext name : %s / %s" % (new_name, ext))
                name = b"%s%s" % (name, ext)
            else:
                # Load and exec address are required, so we need to put the long extension on
                # Ensure the load and exec are the unsigned values:
                if loadaddr < 0:
                    loadaddr += (1<<32)
                loadaddr = loadaddr & 0xFFFFFFFF
                if execaddr < 0:
                    execaddr += (1<<32)
                execaddr = execaddr & 0xFFFFFFFF

                name = b'%s,%08x,%08x' % (name, loadaddr, execaddr)

        # Do the basic conversion
        new_name = self.encode_to_filesystem(name)

        return new_name

    def split(self, path):
        parts = []
        for part in path.split(b'.'):
            if part == b'$':
                parts = [b'$']
            elif part == b'^':
                if len(parts) > 1 and part[-1] != b'^':
                    if part[-1] != b'$':
                        parts = parts[:-1]
                else:
                    parts.append(b'^')
            else:
                parts.append(part)
        return parts

    def canonicalise(self, path):
        cwd_parts = self.split(self._cwd)
        path_parts = self.split(path)
        if not path_parts:
            # This is the CWD
            parts = cwd_parts
        elif path_parts and path_parts[0] == b'$':
            # This is already rooted
            parts = path_parts
        else:
            while path_parts and path_parts[0] == b'^':
                if cwd_parts:
                    cwd_parts = cwd_parts[:-1]
                path_parts = path_parts[1:]
            if cwd_parts:
                parts = cwd_parts + path_parts
            else:
                parts = [b'$']
        return b'.'.join(parts)

    @property
    def cwd(self):
        return self._cwd

    @cwd.setter
    def cwd(self, value):
        dirent = self.find(value)
        if dirent.objtype != 2:
            # FIXME: Find the error number
            raise BBCDirNotFoundError(0, b"'%s' is not a directory" % (dirent.fullpath,))
        self._cwd = dirent.fullpath

    def dirname(self, path):
        parts = self.split(path)
        if parts:
            parts = parts[:-1]
        return self.join(parts)

    def leafname(self, path):
        parts = self.split(path)
        return parts[-1]

    def splitname(self, path):
        parts = self.split(path)
        dirname = b'.'.join(parts[:-1])
        if not dirname:
            dirname = b'$'
        leafname = parts[-1]
        return (dirname, leafname)

    def dir(self, path=None):
        """
        Get the directory object for a given directory.
        """
        if not path:
            path = self.cwd
        else:
            path = self.canonicalise(path)
        #print("dir(%s)" % (path,))
        dir = self.cached.get(path.lower(), None)
        if dir is None:
            (dirname, leafname) = self.splitname(path)
            #print("  dirname=%s leafname=%s" % (dirname, leafname))
            if leafname != b'$':
                parent = self.dir(dirname)
                dir = Directory(self, leafname, parent)
            else:
                dir = Directory(self, leafname, None)

            self.cached[path.lower()] = dir
        return dir

    def find(self, path):
        path = self.canonicalise(path)
        #print("find: path = %r" % (path,))
        (dirname, leafname) = self.splitname(path)
        #print("find: dirname = %r, leafname = %r" % (dirname, leafname))
        dir = self.dir(dirname)
        #print("find: dir = %r" % (dir,))
        dirent = dir[leafname]
        return dirent

    def allocate_filehandle(self, bfh):
        if not self._next_filehandle:
            # FIXME: Fix error number
            raise BBCNoHandlesError(0, b"No more file handles")

        bfh.handle = self._next_filehandle
        self.filehandles[bfh.handle] = bfh
        while self._next_filehandle != 0:
            self._next_filehandle -= 1
            if self._next_filehandle not in self.filehandles:
                break

        if self._next_filehandle == 0:
            # We got to the end and there weren't any handles. Start again
            self._next_filehandle = self.filehandle_max + 1
            while self._next_filehandle != 0:
                self._next_filehandle -= 1
                if self._next_filehandle not in self.filehandles:
                    break
            # IF there were none left, we'll run out of handles here and end up with the next one being 0

    def release_filehandle(self, handle):
        del self.filehandles[handle]
        if handle > self._next_filehandle:
            self._next_filehandle = handle
            # If the handle one higher is also free, the next handle can be that one.
            while handle < self.filehandle_max:
                handle += 1
                if handle not in self.filehandles:
                    self._next_filehandle = handle
                else:
                    break

    def find_filehandle(self, handle):
        bfh = self.filehandles.get(handle, None)
        if not bfh:
            # FIXME: Fix error number
            raise BBCBadHandleError(0, b"Bad file handle")
        return bfh

    def filehandle_range(self):
        return (1, self.filehandle_max)

    def ensure_exists(self, path, loadaddr, execaddr):
        """
        Ensure a file exists, creating it if needed, renaming if not.
        """
        path = self.canonicalise(path)
        (dirname, leafname) = self.splitname(path)
        dir = self.dir(dirname)

        try:
            dirent = dir[leafname]
        except BBCFileNotFoundError:
            # If the file isn't there, we need to create one.
            #print("Try to create new file for %r : %r / %r" % (path, dirname, leafname))
            native_leafname = self.generate_native_filename(leafname, loadaddr, execaddr, 1)
            native_path = os.path.join(dir.fullpath_native, native_leafname)
            #print("Native name = %r" % (native_path,))
            # Create the file
            with open(native_path, 'w') as fh:
                pass
            dir.invalidate()
            dirent = dir[leafname]

        # Now check that the load and exec are consistent
        if dirent.loadaddr != loadaddr or dirent.execaddr != execaddr:
            # The name of the file in the directory doesn't match, so we need to generate a new name
            # This should only really happen if the file we want already exists
            native_leafname = self.generate_native_filename(leafname, loadaddr, execaddr, 1)
            if native_leafname != dirent.native_name:
                native_path = os.path.join(dir.fullpath_native, native_leafname)
                os.rename(dirent.fullpath_native, native_path)

    def fileinfo(self, filename):
        dirent = self.find(filename)
        info_type = dirent.objtype
        info_load = dirent.loadaddr
        info_exec = dirent.execaddr
        info_length = dirent.size
        info_attr = dirent.attributes
        return (info_type, info_load, info_exec, info_length, info_attr)

    def set_fileinfo(self, filename, loadaddr, execaddr, attr):
        # Check that it exists before we apply the set_fileinfo.
        dirent = self.find(filename)

        # Ensure exists will perform any rename that we need to make the file exist with those attributes
        self.ensure_exists(filename, loadaddr, execaddr)

        if dirent.attributes != attr:
            # FIXME: attributes aren't affected yet
            pass

    def delete(self, filename):
        dirent = self.find(filename)
        if dirent.objtype == 1:
            os.unlink(dirent.fullpath_native)
        else:
            os.rmdir(dirent.fullpath_native)

    def open(self, filename, how):
        try:
            dirent = self.find(filename)
        except BBCFileNotFoundError as exc:
            #print("Not found (%s), how=%r" % (filename, how))
            if (how & open_mask) == open_in:
                # Reading the file, so the file has to exist.
                raise

            # Writing, or updating, so we want to create the file first
            #print("  ensure exists")
            self.ensure_exists(filename, self.open_loadaddr, self.open_execaddr)
            dirent = self.find(filename)

        bfh = OpenFile(self, dirent, how)
        self.allocate_filehandle(bfh)
        return bfh.handle

    def close(self, handle):
        if handle == 0:
            # FIXME: Could make this work as on the BBC
            raise BBCError(0, b"Not closing all files")

        bfh = self.find_filehandle(handle)
        bfh.close()
        self.release_filehandle(handle)

    def ptr_write(self, handle, ptr):
        bfh = self.find_filehandle(handle)
        return bfh.ptr(ptr)

    def ptr_read(self, handle):
        bfh = self.find_filehandle(handle)
        return bfh.ptr()

    def ext_read(self, handle):
        bfh = self.find_filehandle(handle)
        return bfh.ext()

    def flush(self, handle):
        bfh = self.find_filehandle(handle)
        bfh.flush()

    def read(self, handle, size):
        bfh = self.find_filehandle(handle)
        return bfh.read(size)

    def write(self, handle, data):
        bfh = self.find_filehandle(handle)
        return bfh.write(data)

    def eof(self, handle):
        bfh = self.find_filehandle(handle)
        return bfh.eof()
