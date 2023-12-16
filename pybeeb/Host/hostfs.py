"""
Implementations of the OS interfaces which communicate with the host (file system specific)
"""

from .base import OSInterface, OSFILE, BBCError
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
        return False

    def write_load(self, filename, info_load, regs, memory):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

    def write_exec(self, filename, info_exec, regs, memory):
        """
        @param filename:    File to operate on
        @param info_exec:   Exec address
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

    def write_attr(self, filename, info_attr, regs, memory):
        """
        @param filename:    File to operate on
        @param info_attr:   File attributes
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

    def read_attr(self, filename, regs, memory):
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
        return None

    def delete(self, filename, regs, memory):
        """
        @param filename:    File to operate on
        @param regs:        Registers object
        @param memory:      Memory object

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

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


def host_fs_interfaces(basedir):
    """
    Construct a list of OS interfaces for filesystems, using a host base directory.
    """
    fs = FS(basedir)
    return [
            lambda: OSFILEhost(fs)
        ]
