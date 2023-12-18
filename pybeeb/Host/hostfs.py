"""
Implementations of the OS interfaces which communicate with the host (file system specific)
"""

from .base import OSInterface, OSFILE, OSFIND, OSBGET, OSBPUT, BBCError
from .fsbbc import FS, BBCFileNotFoundError, open_in, open_out


class OSFILEhost(OSFILE):

    def __init__(self, fs):
        super(OSFILEhost, self).__init__()
        self.fs = fs

    def save(self, filename, src_address, src_length, info_load, info_exec, regs, memory):
        """
        @param filename:    File to operate on
        @param src_address: Start address for save
        @param src_length:  Length of the save
        @param info_load:   Load address
        @param info_exec:   Exec address
        @param info_attr:   File attributes
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        self.fs.ensure_exists(filename, info_load, info_exec)
        handle = self.fs.open(filename, open_out)
        data = memory.readBytes(src_address & 0xFFFF, src_length)
        self.fs.write(handle, data)
        return True

    def write_info(self, filename, info_load, info_exec, info_attr, regs, memory):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param info_exec:   Exec address
        @param info_attr:   File attributes
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        self.fs.set_fileinfo(filename, info_load, info_exec, info_attr)
        return True

    def write_load(self, filename, info_load, regs, memory):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        (info_type, _, info_exec, info_length, info_attr) = self.fs.fileinfo(filename)
        self.fs.set_fileinfo(filename, info_load, info_exec, info_attr)
        return True

    def write_exec(self, filename, info_exec, regs, memory):
        """
        @param filename:    File to operate on
        @param info_exec:   Exec address
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        (info_type, info_load, _, info_length, info_attr) = self.fs.fileinfo(filename)
        self.fs.set_fileinfo(filename, info_load, info_exec, info_attr)
        return True

    def write_attr(self, filename, info_attr, regs, memory):
        """
        @param filename:    File to operate on
        @param info_attr:   File attributes
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        (info_type, info_load, info_exec, info_length, _) = self.fs.fileinfo(filename)
        self.fs.set_fileinfo(filename, info_load, info_exec, info_attr)
        return True

    def read_info(self, filename, regs, memory):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param info_exec:   Exec address
        @param info_attr:   File attributes
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    None if not handled,
                    Tuple of (info_type, info_load, info_exec, info_length, info_attr) if handled
        """
        (info_type, info_load, info_exec, info_length, info_attr) = self.fs.fileinfo(filename)
        return (info_type, info_load, info_exec, info_length, info_attr)

    def delete(self, filename, regs, memory):
        """
        @param filename:    File to operate on
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        self.fs.delete(filename)
        return True

    def load(self, filename, load_address, regs, memory):
        """
        @param filename:    File to operate on
        @param regs:        Registers object
        @param memory:      Memory object

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
            memory.writeBytes(load_address & 0xFFFF, data)
        finally:
            if handle:
                self.fs.close(handle)

        return (info_type, info_load, info_exec, info_length, info_attr)


class OSFINDhost(OSFIND):

    def __init__(self, fs):
        super(OSFINDhost, self).__init__()
        self.fs = fs

    def open(self, op, filename, regs, memory):
        """
        Open a file for reading, writing or update.

        @param op:          operation to perform:
                                &40: input only
                                &80: output only
                                &C0: input and output
        @param filename:    file to open

        @return:    file handle, or 0 if failed to open, or None if not handled
        """
        try:
            handle = self.fs.open(filename, op)
        except BBCFileNotFoundError as exc:
            handle = 0

        return handle

    def close(self, fh, regs, memory):
        """
        Close a previously open file.

        @param fh:  file handle to close, or 0 to close all files.

        @return:    True if handled; False if not handled.
        """
        self.fs.close(fh)
        return True


class OSBGEThost(OSBGET):

    def __init__(self, fs):
        super(OSBGEThost, self).__init__()
        self.fs = fs

    def osbget(self, fh, regs, memory):
        """
        Handle BGET, returning the byte read.

        @param fh:  File handle to read

        @return:    byte read, -1 if at file end, or None if not handled
        """
        data = self.fs.read(fh, 1)
        if not data:
            return -1
        return data[0]


class OSBPUThost(OSBPUT):

    def __init__(self, fs):
        super(OSBPUThost, self).__init__()
        self.fs = fs

    def osbput(self, b, fh, regs, memory):
        """
        Handle BPUT, writing the supplied byte to a file..

        @param fh:  File handle to write to
        @param b:   Byte to write

        @return:    True if handled, False if not handled.
        """
        #print("bput %r" % (b,))
        data = bytes(bytearray([b]))
        self.fs.write(fh, data)
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
        ]
