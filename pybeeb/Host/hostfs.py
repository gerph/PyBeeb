"""
Implementations of the OS interfaces which communicate with the host (file system specific)
"""

from .base import OSInterface, OSFILE, OSFIND, OSBGET, OSBPUT, OSARGS, OSFSC, OSBYTE, OSCLI, BBCError
from .fsbbc import FS, BBCFileNotFoundError, open_in, open_out


class OSFILEhost(OSFILE):

    def __init__(self, fs):
        super(OSFILEhost, self).__init__()
        self.fs = fs

    def save(self, filename, src_address, src_length, info_load, info_exec, pb):
        """
        @param filename:    File to operate on
        @param src_address: Start address for save
        @param src_length:  Length of the save
        @param info_load:   Load address
        @param info_exec:   Exec address
        @param info_attr:   File attributes
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        self.fs.ensure_exists(filename, info_load, info_exec)
        handle = self.fs.open(filename, open_out)
        data = pb.memory.readBytes(src_address & 0xFFFF, src_length)
        self.fs.write(handle, data)
        return True

    def write_info(self, filename, info_load, info_exec, info_attr, pb):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param info_exec:   Exec address
        @param info_attr:   File attributes
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        self.fs.set_fileinfo(filename, info_load, info_exec, info_attr)
        return True

    def write_load(self, filename, info_load, pb):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        (info_type, _, info_exec, info_length, info_attr) = self.fs.fileinfo(filename)
        self.fs.set_fileinfo(filename, info_load, info_exec, info_attr)
        return True

    def write_exec(self, filename, info_exec, pb):
        """
        @param filename:    File to operate on
        @param info_exec:   Exec address
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        (info_type, info_load, _, info_length, info_attr) = self.fs.fileinfo(filename)
        self.fs.set_fileinfo(filename, info_load, info_exec, info_attr)
        return True

    def write_attr(self, filename, info_attr, pb):
        """
        @param filename:    File to operate on
        @param info_attr:   File attributes
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        (info_type, info_load, info_exec, info_length, _) = self.fs.fileinfo(filename)
        self.fs.set_fileinfo(filename, info_load, info_exec, info_attr)
        return True

    def read_info(self, filename, pb):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param info_exec:   Exec address
        @param info_attr:   File attributes
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    None if not handled,
                    Tuple of (info_type, info_load, info_exec, info_length, info_attr) if handled
        """
        (info_type, info_load, info_exec, info_length, info_attr) = self.fs.fileinfo(filename)
        return (info_type, info_load, info_exec, info_length, info_attr)

    def delete(self, filename, pb):
        """
        @param filename:    File to operate on
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        self.fs.delete(filename)
        return True

    def load(self, filename, load_address, pb):
        """
        @param filename:    File to operate on
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    None if not handled,
                    Tuple of (info_type, info_load, info_exec, info_length, info_attr) if handled
        """
        handle = None
        try:
            (info_type, info_load, info_exec, info_length, info_attr) = self.fs.fileinfo(filename)
            if info_type == 0:
                # FIXME: Error number
                raise BBCFileNotFoundError(0, "File not found")
            if info_type == 2:
                # FIXME: Error number
                raise BBCFileNotFoundError(0, "Is a directory")

            if load_address is None:
                load_address = info_load & 0xFFFF

            handle = self.fs.open(filename, open_in)
            size = self.fs.ext_read(handle)
            data = self.fs.read(handle, size)
            pb.memory.writeBytes(load_address & 0xFFFF, data)
        finally:
            if handle:
                self.fs.close(handle)

        return (info_type, info_load, info_exec, info_length, info_attr)


class OSFINDhost(OSFIND):

    def __init__(self, fs):
        super(OSFINDhost, self).__init__()
        self.fs = fs

    def open(self, op, filename, pb):
        """
        Open a file for reading, writing or update.

        @param op:          operation to perform:
                                &40: input only
                                &80: output only
                                &C0: input and output
        @param filename:    file to open
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    file handle, or 0 if failed to open, or None if not handled
        """
        try:
            handle = self.fs.open(filename, op)
        except BBCFileNotFoundError as exc:
            handle = 0

        return handle

    def close(self, fh, pb):
        """
        Close a previously open file.

        @param fh:  file handle to close, or 0 to close all files.
        @param pb:  Emulator object, containing `regs` and `memory`

        @return:    True if handled; False if not handled.
        """
        self.fs.close(fh)
        return True


class OSBGEThost(OSBGET):

    def __init__(self, fs):
        super(OSBGEThost, self).__init__()
        self.fs = fs

    def osbget(self, fh, pb):
        """
        Handle BGET, returning the byte read.

        @param fh:  File handle to read
        @param pb:  Emulator object, containing `regs` and `memory`

        @return:    byte read, -1 if at file end, or None if not handled
        """
        data = self.fs.read(fh, 1)
        if not data:
            return -1
        return bytearray(data[0])[0]


class OSBPUThost(OSBPUT):

    def __init__(self, fs):
        super(OSBPUThost, self).__init__()
        self.fs = fs

    def osbput(self, b, fh, pb):
        """
        Handle BPUT, writing the supplied byte to a file..

        @param fh:  File handle to write to
        @param b:   Byte to write
        @param pb:  Emulator object, containing `regs` and `memory`

        @return:    True if handled, False if not handled.
        """
        #print("bput %r" % (b,))
        data = bytes(bytearray([b]))
        self.fs.write(fh, data)
        return True


class OSARGShost(OSARGS):

    def __init__(self, fs):
        super(OSARGShost, self).__init__()
        self.fs = fs

    def read_ptr(self, fh, pb):
        """
        Read PTR#.

        @param fh:      File handle to read
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    PTR for the file, or None if not handled
        """
        ptr = self.fs.ptr_read(fh)
        return ptr

    def read_ext(self, fh, pb):
        """
        Read EXT#.

        @param fh:      File handle to read
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    EXT for the file, or None if not handled
        """
        ext = self.fs.ext_read(fh)
        return ext

    def write_ptr(self, fh, ptr, pb):
        """
        Write PTR#.

        @param fh:      File handle to read
        @param ptr:     New PTR value
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    True if handled, False if not handled
        """
        self.fs.ptr_write(fh, ptr)
        return True

    def flush_file(self, fh, pb):
        """
        Flush file to storage.

        @param fh:      File handle to read
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    True if handled, False if not handled
        """
        self.fs.flush(fh)
        return True

    def flush_all_files(self, pb):
        """
        Flush all files to storage

        @param fh:      File handle to read
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    True if handled, False if not handled
        """
        return False

    def read_current_filesystem(self, pb):
        """
        Read the current filesystem.

        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    Filesystem number, or None is not handled
        """
        return 4    # FS_DFS

    def read_cli_args(self, pb):
        """
        Read the CLI arguments.

        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    Address of CLI arguments, or None is not handled
        """
        return None


class OSFSChost(OSFSC):

    def __init__(self, fs):
        super(OSFSChost, self).__init__()
        self.fs = fs

    def dispatch_parameters(self, pb):
        """
        Decode the parameters for the address.
        """
        address = pb.regs.x | (pb.regs.y << 8)
        return [pb.regs.a, address, pb]

    def opt(self, x, y, pb):
        """
        *OPT X, Y issued

        @param x, y:    Parameters to *Opt
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        return False

    def eof(self, fh, pb):
        """
        EOF#fh check

        @param fh:      File handle
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if EOF,
                        False if not EOF,
                        None if not handled
        """
        return self.fs.eof(fh)

    def slash(self, cli, pb):
        """
        */<command> issued.

        @param cli:     CLI to execute
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        return False

    def ukcommand(self, cli, pb):
        """
        Unknown command issued

        @param cli:     Command issued
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        return False

    def run(self, run, pb):
        """
        *Run issued.

        @param run:     Command to run
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        return False

    def cat(self, path, pb):
        """
        *Cat issued

        @param path:    Directory name, or empty for CWD
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        dir = self.fs.dir(path)
        files = dir.files
        longest_name = max(len(dirent.name) for dirent in files.values())
        longest_name = max(10, longest_name)

        pb.mos.write("Dir.   %s\n\n" % (dir.fullpath,))

        ordered = sorted(files.items())
        width = 40
        # FIXME: Make the width configurable (or read from the mode vars?)
        x = 0
        for key, dirent in ordered:
            text = "%-*s  " % (longest_name, dirent.name)
            attr = []
            if dirent.objtype == 2:
                attr.append('D')

            if dirent.attributes & 8:
                attr.append('L')
            if dirent.attributes & 4:
                attr.append('E')
            if dirent.attributes & 2:
                attr.append('W')
            if dirent.attributes & 1:
                attr.append('R')
            attr.append('/')
            if dirent.attributes & 0x80:
                attr.append('L')
            if dirent.attributes & 0x40:
                attr.append('E')
            if dirent.attributes & 0x20:
                attr.append('W')
            if dirent.attributes & 0x10:
                attr.append('R')

            text += "%-10s  " % (''.join(attr),)

            x += len(text)
            if x > width:
                pb.mos.write(b'\n')
                x = len(text)

            pb.mos.write(text)

        if x != 0:
            pb.mos.write(b'\n')

        pb.mos.write("\n%s files\n" % (len(files),))
        return True

    def fs_starting(self, pb):
        """
        New FS is starting.

        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        return False

    def get_handle_range(self, pb):
        """
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        None if not handled
                        Tuple of (low handle, high handle) if handled
        """
        return self.fs.handle_range()

    def star_command(self, pb):
        """
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        return False


class OSBYTEhost(OSBYTE):

    def __init__(self, fs):
        super(OSBYTEhost, self).__init__()
        self.fs = fs

        self.dispatch[0x7F] = self.osbyte_eof

    def osbyte_eof(self, a, x, y, pb):
        fh = x
        if self.fs.eof(fh):
            pb.regs.x = 0xFF
        else:
            pb.regs.x = 0
        return True


class OSCLIhost(OSCLI):

    def __init__(self, fs):
        super(OSCLIhost, self).__init__()
        self.fs = fs

        self.commands_dispatch['DIR'] = self.cmd_dir

    def cmd_dir(self, args, pb):
        self.fs.cwd = args
        return True


def host_fs_interfaces(basedir):
    """
    Construct a list of OS interfaces for filesystems, using a host base directory.
    """
    fs = FS(basedir)
    return [
            lambda: OSFILEhost(fs),
            lambda: OSFINDhost(fs),
            lambda: OSBGEThost(fs),
            lambda: OSBPUThost(fs),
            lambda: OSARGShost(fs),
            lambda: OSFSChost(fs),
            lambda: OSBYTEhost(fs),
            lambda: OSCLIhost(fs),
        ]
