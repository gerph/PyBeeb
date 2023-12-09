"""
Base classes for the implementations of host interfaces.
"""

import sys


__all__ = (
        'BBCError',
        'InputEOFError',
        'OSInterface',
        'OSBYTE',
        'OSWORD',
        'OSCLI',
        'OSWRCH',
        'OSRDCH',
        'OSFILE',
        'OSFIND',
        'OSARGS',
        'OSBPUT',
        'OSBGET',
    )


class BBCError(Exception):

    def __init__(self, errnum, errmess):
        self.errnum = errnum
        self.errmess = errmess
        super(BBCError, self).__init__(errmess, errnum)


class InputEOFError(Exception):
    pass


class OSInterface(object):
    code = 0x0000
    vector = 0x200

    def __init__(self):
        """
        Initialise the interface.
        """
        pass

    def start(self):
        """
        System is starting; prepare the interface for use.
        """
        pass

    def stop(self):
        """
        System is stopping; shut down the interface.
        """
        pass

    def call(self, regs, memory):
        """
        Call the interface with a given set of parameters.

        The Registers and Memory will be updated on return.

        May raise exception BBCError to indicate that an error should be reported.

        @param regs:        Registers object, containing a, x, y, pc, and sp properties + the flags
        @param memory:      Memory object, containing the (read|write)(Byte|Bytes|Word|SignedByte) methods

        @return:    True if the call has been handled (return from interface),
                    False if call should continue at the code execution point
        """
        return False


class OSWRCH(OSInterface):
    code = 0xE0A4
    vector = 0x020E

    def call(self, regs, memory):
        return self.writec(regs.a)

    def writec(self, ch):
        """
        Write a BBC VDU code to the output stream.
        """
        return False


class OSRDCH(OSInterface):
    code = 0xDEC5
    vector = 0x0210

    def call(self, regs, memory):
        ch = self.readc()
        if ch is None:
            return False

        ch = ord(ch)
        if ch == 27:
            regs.carry = True

            # Bit of a hack as we don't have interrupts
            # Set the escape flag
            memory.writeByte(0xFF, 0x80)
        else:
            regs.carry = False
        regs.a = ch

        # Return immediately with an RTS
        return True

    def readc(self):
        return None


class OSCLI(OSInterface):
    code = 0xDF89
    vector = 0x0208

    def call(self, regs, memory):
        xy = regs.x | (regs.y << 8)
        cli = memory.readString(xy)
        while cli[0] == '*':
            cli = cli[1:]
        if ' ' in cli:
            (command, args) = cli.split(' ', 1)
        else:
            command = cli
            args = ''

        return self.command(command.upper(), args)

    def command(self, command, args):
        return False


class OSBYTE(OSInterface):
    code = 0xE772
    vector = 0x020A

    def __init__(self):
        super(OSBYTE, self).__init__()

        # The dispatch dictionary contains the functions that should be
        # dispatched to handle OSBYTE calls.
        # The keys in the dictionary may be one of:
        #   (A, X, Y)
        #   (A, X)
        #   A
        # The value of the first matched key will be used as the
        # dispatcher.
        # If no matching key exists, the method `osbyte` will be used.
        # The dispatcher used will be called with the parameters
        # `(A, X, Y, regs, memory)`.
        self.dispatch = {
            }

    def call(self, regs, memory):
        dispatcher = self.dispatch.get((regs.a, regs.x, regs.y), None)
        if dispatcher is None:
            dispatcher = self.dispatch.get((regs.a, regs.x), None)
            if dispatcher is None:
                dispatcher = self.dispatch.get(regs.a, None)
                if dispatcher is None:
                    dispatcher = self.osbyte
        return dispatcher(regs.a, regs.x, regs.y, regs, memory)

    def osbyte(self, a, x, y, regs, memory):
        return False


class OSWORD(OSInterface):
    code = 0xE7EB
    vector = 0x020C

    def __init__(self):
        super(OSWORD, self).__init__()

        # The dispatch dictionary contains the functions that should be
        # dispatched to handle OSWORD calls.
        # The keys in the dictionary may the value of the A register.
        # If no matching key exists, the method `osword` will be used.
        # The dispatcher used will be called with the parameters
        # `(a, address, regs, memory)`.
        self.dispatch = {}

    def call(self, regs, memory):
        dispatcher = self.dispatch.get(regs.a, None)
        if dispatcher is None:
            dispatcher = self.osword

        address = regs.x | (regs.y << 8)
        return dispatcher(regs.a, address, regs, memory)

    def osword(self, a, address, regs, memory):
        return False


class OSFILE(OSInterface):
    code = 0xF27D
    vector = 0x0212

    def __init__(self):
        super(OSFILE, self).__init__()

        # The dispatch dictionary contains the functions that should be
        # dispatched to handle OSFILE calls.
        # The keys in the dictionary may the value of the A register.
        # If no matching key exists, the method `osfile` will be used.
        # The dispatcher used will be called with the parameters
        # `(a, filename, address, regs, memory)`.
        self.dispatch = {}

    def call(self, regs, memory):
        dispatcher = self.dispatch.get(regs.a, None)
        if dispatcher is None:
            dispatcher = self.osfile

        address = regs.x | (regs.y << 8)
        filename_ptr = memory.readWord(address)
        filename = memory.readString(filename_ptr)
        return dispatcher(regs.a, filename, address, regs, memory)

    def osfile(self, op, filename, address, regs, memory):
        """
        Handle an OSFILE call.

        Memory block contains:

        00  Address of filename, terminated by RETURN &0D
        01
        02  Load address of the file.
        03  Low byte first.
        04
        05
        06  Execution address of the file.
        07  Low byte first.
        08
        09
        0A  Start address of data for save,
        0B  length of file otherwise.
        0C  Low byte first.
        0D
        0E  End address of data for save,
        0F  file attributes otherwise.
        10  Low byte first.
        11

        Reason codes in A:

        A=0     Save a block of memory as a file using the information provided in the parameter block.
        A=1     Write the information in the parameter block to the catalogue entry for an existing file
                (i.e. file name and addresses).
        A=2     Write the load address (only) for an existing file.
        A=3     Write the execution address (only) for an existing file.
        A=4     Write the attributes (only) for an existing file.
        A=5     Read a file's catalogue information, with the file type returned in the accumulator.
                The information is written to the parameter block.
        A=6     Delete the named file.
        A=&FF   Load the named file, the address to which the file is loaded being determined by the
                lowest byte of the execution address in the control block (XY+6).
                If this byte is zero, the address given in the controlblock is used,
                otherwise the file's own load address is used.

        @param op:          operation code from the A register
        @param filename:    The filename to work with
        @param address:     The address of the block for file operations
        @param regs:        Registers
        @param memory:      Memory access

        @return:        True if handled
                        False if not handled
        """
        handled = False

        if op == 0:
            # Save
            src_address = memory.readLongWord(address + 10)
            src_length = memory.readLongWord(address + 14) - src_address
            info_load = memory.readLongWord(address + 2)
            info_exec = memory.readLongWord(address + 6)
            handled = self.save(filename, src_address, src_length, info_load, info_exec, regs, memory)

        elif op == 1:
            # Write load+exec+attr
            info_load = memory.readLongWord(address + 2)
            info_exec = memory.readLongWord(address + 6)
            info_attr = memory.readLongWord(address + 14)
            handled = self.write_info(filename, info_load, info_exec, info_attr, regs, memory)

        elif op == 2:
            # Write load
            info_load = memory.readLongWord(address + 2)
            handled = self.write_load(filename, info_load, regs, memory)

        elif op == 3:
            # Write exec
            info_exec = memory.readLongWord(address + 6)
            handled = self.write_exec(filename, info_exec, regs, memory)

        elif op == 4:
            # Write attr
            info_attr = memory.readLongWord(address + 14)
            handled = self.write_attr(filename, info_attr, regs, memory)

        elif op == 5:
            # Read load+exec+attr
            result = self.read_attr(filename, regs, memory)
            if result:
                handled = True
                (info_type, info_load, info_exec, info_length, info_attr) = result
                memory.writeLongWord(address + 2, info_load)
                memory.writeLongWord(address + 6, info_exec)
                memory.writeLongWord(address + 10, info_length)
                memory.writeLongWord(address + 14, info_attr)
                regs.a = info_type
            else:
                handled = False

        elif op == 6:
            # Delete
            handled = self.delete(filename, regs, memory)

        elif op == 255:
            # Load
            if memory.readByte(address + 6) == 0:
                load_address = None
            else:
                load_address = memory.readLongWord(address + 2)
            result = self.load(filename, load_address, regs, memory)
            if result:
                handled = True
                (info_type, info_load, info_exec, info_length, info_attr) = result
                memory.writeLongWord(address + 2, info_load)
                memory.writeLongWord(address + 6, info_exec)
                memory.writeLongWord(address + 10, info_length)
                memory.writeLongWord(address + 14, info_attr)
                regs.a = info_type
            else:
                handled = False

        return handled

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
        return False

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
        return None



class OSARGS(OSInterface):
    code = 0xF1E8
    vector = 0x0214

    def __init__(self):
        super(OSARGS, self).__init__()

        # The dispatch dictionary contains the functions that should be
        # dispatched to handle OSARGS calls.
        # The keys in the dictionary may the value of the A register.
        # If no matching key exists, the method `osargs` will be used.
        # The dispatcher used will be called with the parameters
        # `(a, fh, address, regs, memory)`.
        self.dispatch = {}

    def call(self, regs, memory):
        dispatcher = self.dispatch.get((regs.a, regs.y), None)
        if dispatcher is None:
            dispatcher = self.dispatch.get(regs.a, None)
            if dispatcher is None:
                dispatcher = self.osargs

        fh = regs.y
        address = regs.x
        return dispatcher(regs.a, fh, address, regs, memory)

    def osargs(self, op, fh, address, regs, memory):
        """
        Handle OSARGS call for a given reason code and file handle.

        If fh is 0:
            A = 0:  Return current filesystem
                1:  Return CLI args
                255: Flush all files to storage
        else:
            A = 0:  Return PTR#
                1:  Write PTR#
                2:  Read EXT#
                255: Flush file to storage
        """
        handled = False
        if fh == 0:
            # Filehandle = 0
            if op == 0x00:
                result = self.read_current_filesystem(regs, memory)
                handled = result is not None
                if handled:
                    regs.a = result

            elif op == 0x01:
                # Read CLI args
                result = self.read_cli_args(regs, memory)
                handled = result is not None
                if handled:
                    memory.writeLongWord(address, result)

            elif op == 0xFF:
                # Flush all files
                handled = self.flush_all_files(regs, memory)

        else:
            # Filehandle supplied
            if op == 0x00:
                # Read PTR#
                result = self.read_ptr(fh, regs, memory)
                handled = result is not None
                if handled:
                    memory.writeLongWord(address, result)

            elif op == 0x01:
                # Write PTR#
                ptr = memory.readLongWord(address)
                handled = self.write_ptr(fh, ptr, regs, memory)

            elif op == 0x02:
                # Read EXT#
                handled = self.read_ext(fh, regs, memory)
                handled = result is not None
                if handled:
                    memory.writeLongWord(address, result)

            elif op == 0xFF:
                # Flush file to storage
                handled = self.flush_file(fh, regs, memory)

        return False

    def read_ptr(self, fh, regs, memory):
        """
        Read PTR#.

        @param fh:      File handle to read
        @param regs:    Registers object
        @param memory:  Memory object

        @return:    PTR for the file, or None if not handled
        """
        return None

    def read_ext(self, fh, regs, memory):
        """
        Read EXT#.

        @param fh:      File handle to read
        @param regs:    Registers object
        @param memory:  Memory object

        @return:    EXT for the file, or None if not handled
        """
        return None

    def write_ptr(self, fh, ptr, regs, memory):
        """
        Write PTR#.

        @param fh:      File handle to read
        @param ptr:     New PTR value
        @param regs:    Registers object
        @param memory:  Memory object

        @return:    True if handled, False if not handled
        """
        return None

    def flush_file(self, fh, regs, memory):
        """
        Flush file to storage.

        @param fh:      File handle to read
        @param regs:    Registers object
        @param memory:  Memory object

        @return:    True if handled, False if not handled
        """
        return False

    def flush_all_files(self, regs, memory):
        """
        Flush all files to storage

        @param fh:      File handle to read
        @param regs:    Registers object
        @param memory:  Memory object

        @return:    True if handled, False if not handled
        """
        return False

    def read_current_filesystem(self, regs, memory):
        """
        Read the current filesystem.

        @param regs:    Registers object
        @param memory:  Memory object

        @return:    Filesystem number, or None is not handled
        """
        return None

    def read_cli_args(self, regs, memory):
        """
        Read the CLI arguments.

        @param regs:    Registers object
        @param memory:  Memory object

        @return:    Address of CLI arguments, or None is not handled
        """
        return None


class OSBGET(OSInterface):
    code = 0xF4C9
    vector = 0x0216

    def call(self, regs, memory):
        fh = regs.y
        b = self.osbget(fh, regs, memory)
        if b is None:
            return False

        if b == -1:
            regs.carry = True
        else:
            regs.carry = False
            regs.a = b
        return True

    def osbget(self, fh, regs, memory):
        """
        Handle BGET, returning the byte read.

        @param fh:  File handle to read

        @return:    byte read, -1 if at file end, or None if not handled
        """
        return None


class OSBPUT(OSInterface):
    code = 0xF529
    vector = 0x0218

    def call(self, regs, memory):
        fh = regs.y
        b = regs.a
        handled = self.osbput(b, fh, regs, memory)
        return handled

    def osbput(self, b, fh, regs, memory):
        """
        Handle BPUT, writing the supplied byte to a file..

        @param fh:  File handle to write to
        @param b:   Byte to write

        @return:    True if handled, False if not handled.
        """
        return False


class OSFIND(OSInterface):
    code = 0xF3CA
    vector = 0x0218

    def call(self, regs, memory):
        a = regs.a
        if a == 0:
            fh = regs.y
            return self.close(fh, regs, memory)

        address = regs.x | (regs.y << 8)
        filename_ptr = memory.readWord(address)
        filename = memory.readString(filename_ptr)
        fh = self.open(a, filename, regs, memory)
        if fh is None:
            return False
        regs.a = fh
        return True

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
        print("open(%i, %r)" % (op, filename))
        return None

    def close(self, fh, regs, memory):
        """
        Close a previously open file.

        @param fh:  file handle to close, or 0 to close all files.

        @return:    True if handled; False if not handled.
        """
        return False
