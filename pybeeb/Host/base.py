"""
Base classes for the implementations of host interfaces.

Each base class is derived from the OSInterface class, which has a standard interface
for handling the entry point.

The following properties are defined on the object:

* `code`: The default address of the handler for these entry points, which is usually
          stored in the vector entry point. For the file system interfaces, the code
          address is for the Tape file system, so *TAPE will reselect these interfaces.
* `vector`: The address of the the vector for this interface.
* `dispatch`: Some objects contain a dispatch table mapping the conditions of the
          registers to functions.
          This is used by the interfaces which have operation codes in A (and X or Y).
* `dispatch_default`: Default dispatch entry point if none of the `dispatch` mappings
          are matched.

The following methods are defined on the object:

* `__init__`: creates the interface object.
* `start`: should be called when the system is started and the interface is being
           prepared for use.
* `stop`: should be called when the system is destroyed, or the interface is no longer
          required.
* `call`: should be called when the OS interface is invoked. It will be passed two
          objects - a Registers object, and a Memory object. These may be used to
          interact with the emulator system. Returns False to continue execution with
          the default handler, or True if the caller should return from the vector (as
          if RTS had been executed).
          The default `call` method will look up the operation codes using the
          `dispatch` map and call to the `dispatch_default` function if none match.
* `dispatch_parameters`: will interpret the registers into a default set of parameters
          for the dispatch call.

Other methods may be provided for individual interfaces to perform specific operations.
Consult the class implementation for more details on these additional methods.

To provide implementations, a new class should be created based on these base classes.
The child class may provide a new implementation of the `start` and `stop` to initialise
the state of the interface. New implementations may be provided for the `call` method,
or the `dispatch` table can be updated to provide alternative handlers for operation
codes.

The OSInterface should return the error BBCError to report errors. The caller should
trap these and trigger an error through the BRK mechanism.

The input system should report InputEOFError if an EOF condition is encountered when
reading input from the user.
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
        'OSGBPB',
        'OSFSC',
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

        # The dispatch dictionary contains the functions that should be
        # dispatched to handle the OSInterface calls.
        # The keys in the dictionary may be one of:
        #   (A, X, Y)
        #   (A, X)
        #   A
        # The value of the first matched key will be used as the
        # dispatcher.
        # If no matching key exists, the method `dispatch_default` will
        # be used.
        # The dispatcher used will be called with the parameters
        # returned by the `dispatch_parameters` method. By default these
        # are:
        #   (A, X, Y, regs, memory)
        self.dispatch = {}
        self.dispatch_default = None

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

    def dispatch_parameters(self, regs, memory):
        """
        Prepare a set of parameters to pass to the dispatcher.

        @param regs:        Registers object, containing a, x, y, pc, and sp properties + the flags
        @param memory:      Memory object, containing the (read|write)(Byte|Bytes|Word|SignedByte) methods

        @return:    list of parameters to pass to the dispatcher
        """
        return [regs.a, regs.x, regs.y, regs, memory]

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
        dispatcher = self.dispatch.get((regs.a, regs.x, regs.y), None)
        if dispatcher is None:
            dispatcher = self.dispatch.get((regs.a, regs.x), None)
            if dispatcher is None:
                dispatcher = self.dispatch.get(regs.a, None)
                if dispatcher is None:
                    dispatcher = self.dispatch_default
        if dispatcher:
            params = self.dispatch_parameters(regs, memory)
            return dispatcher(*params)
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
        while cli[0:1] == b'*':
            cli = cli[1:]
        if b' ' in cli:
            (command, args) = cli.split(b' ', 1)
        else:
            command = cli
            args = b''

        return self.command(command.upper(), args)

    def command(self, command, args):
        return False


class OSBYTE(OSInterface):
    code = 0xE772
    vector = 0x020A

    def __init__(self):
        super(OSBYTE, self).__init__()
        self.dispatch_default = self.osbyte

    def osbyte(self, a, x, y, regs, memory):
        return False


class OSWORD(OSInterface):
    code = 0xE7EB
    vector = 0x020C

    def __init__(self):
        super(OSWORD, self).__init__()

        # The dispatcher used will be called with the parameters
        #   (a, address, regs, memory)
        self.dispatch_default = self.osword

    def dispatch_parameters(self, regs, memory):
        """
        Decode the paramters for the address.
        """
        address = regs.x | (regs.y << 8)
        return [regs.a, address, regs, memory]

    def osword(self, a, address, regs, memory):
        return False


class OSFILE(OSInterface):
    code = 0xF27D
    vector = 0x0212

    def __init__(self):
        super(OSFILE, self).__init__()

        # The default dispatcher is called with:
        #   (op, filename, address, regs, memory)
        self.dispatch_default = self.osfile

    def dispatch_parameters(self, regs, memory):
        address = regs.x | (regs.y << 8)
        filename_ptr = memory.readWord(address)
        filename = memory.readString(filename_ptr)
        return [regs.a, filename, address, regs, memory]

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

    def call(self, regs, memory):
        # NOTE: We do not use the standard dispatcher mechanism here
        #       because the primary discriminator is the Y register,
        #       rather than the A register.
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

    def __init__(self):
        super(OSFIND, self).__init__()
        # Handle the close dispatch through the dispatch table
        self.dispatch[0x00] = self.call_close
        self.dispatch_default = self.call_open

    def call_close(self, a, x, y, regs, memory):
        return self.close(fh=y, regs=regs, memory=memory)

    def call_open(self, a, x, y, regs, memory):
        address = x | (y << 8)
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
        return None

    def close(self, fh, regs, memory):
        """
        Close a previously open file.

        @param fh:  file handle to close, or 0 to close all files.

        @return:    True if handled; False if not handled.
        """
        return False


class OSGBPB(OSInterface):
    code = 0xFFA6
    vector = 0x021A

    def __init__(self):
        super(OSGBPB, self).__init__()
        self.dispatch[0x01] = self.call_put_bytes
        self.dispatch[0x02] = self.call_put_bytes
        self.dispatch[0x03] = self.call_get_bytes
        self.dispatch[0x04] = self.call_get_bytes
        self.dispatch[0x05] = self.call_get_media_title
        self.dispatch[0x06] = lambda op, address, regs, memory: self.call_get_csd_lib(op, address, regs, memory, csd=True)
        self.dispatch[0x07] = lambda op, address, regs, memory: self.call_get_csd_lib(op, address, regs, memory, csd=False)
        self.dispatch[0x08] = self.call_get_filenames
        self.dispatch_default = self.osgbpb

    def dispatch_parameters(self, regs, memory):
        """
        Decode the parameters for the address.
        """
        address = regs.x | (regs.y << 8)
        return [regs.a, address, regs, memory]

    def osgbpb(self, op, address, regs, memory):
        """
        The control block format is:

        00 File handle
        01 Pointer to data in either I/O processor or Tube
        02   processor.
        03 Low byte first.
        04
        05 Number of bytes to transfer
        06 Low byte first.
        07
        08
        09 Sequential pointer value to be used for transfer
        0A Low byte first.
        0B
        0C

        Operation codes:

        01 Put bytes at pointer
        02 Put bytes
        03 Get bytes from pointer
        04 Get bytes
        05 Get media title and option
        06 Read CSD and device
        07 Read Lib and device
        08 Read names from CSD
        """
        return False

    def call_put_bytes(self, op, address, regs, memory):
        """
        Put bytes (at a given location).
        """
        fh = memory.readByte(address)
        dataaddr = memory.readLongWord(address + 1)
        datalen = memory.readLongWord(address + 5)
        if op == 1:
            ptr = memory.readLongWord(address + 9)
        else:
            ptr = None
        data = memory.readBytes(dataaddr, datalen)
        result = self.put_bytes(fh, data, ptr, regs, memory)
        if result:
            (transferred, newptr) = result
            if transferred != datalen:
                regs.carry = True
                memory.writeLongWord(address + 5, datalen - transferred)
            else:
                regs.carry = False
            memory.writeLongWord(address + 1, dataaddr + transferred)
            memory.writeLongWord(address + 9, newptr)
            handled = True
        else:
            handled = False
        return handled

    def call_get_bytes(self, op, address, regs, memory):
        """
        Put bytes (at a given location).
        """
        fh = memory.readByte(address)
        dataaddr = memory.readLongWord(address + 1)
        datalen = memory.readLongWord(address + 5)
        if op == 1:
            ptr = memory.readLongWord(address + 9)
        else:
            ptr = None
        result = self.get_bytes(fh, datalen, ptr, regs, memory)
        if result:
            (data, newptr) = result
            transferred = len(data)
            if transferred != datalen:
                regs.carry = True
                memory.writeLongWord(address + 5, datalen - transferred)
            else:
                regs.carry = False
            memory.writeLongWord(address + 1, dataaddr + transferred)
            memory.writeLongWord(address + 9, newptr)
            memory.writeBytes(dataaddr, data)
            handled = True
        else:
            handled = False
        return handled

    def call_get_media_title(self, op, address, regs, memory):
        """
        Get media title and option as <len><title><option>
        """
        dataaddr = memory.readLongWord(address + 1)
        datalen = memory.readLongWord(address + 5)
        result = self.get_media_title(regs, memory)
        if result:
            (title, option) = result
            transferred = 1 + len(title) + 1
            if transferred != datalen:
                regs.carry = True
                memory.writeLongWord(address + 5, datalen - transferred)
            else:
                regs.carry = False
            data = bytearray([len(title)]) + bytearray(title) + bytearray(option)
            memory.writeLongWord(address + 1, dataaddr + transferred)
            memory.writeLongWord(address + 9, transferred)
            memory.writeBytes(dataaddr, data)
            handled = True
        else:
            handled = False
        return handled

    def call_get_csd_lib(self, op, address, regs, memory, csd):
        """
        Get CSD/library and device as <len><device><len><csd>
        """
        dataaddr = memory.readLongWord(address + 1)
        datalen = memory.readLongWord(address + 5)
        if csd:
            result = self.get_csd(regs, memory)
        else:
            result = self.get_lib(regs, memory)
        if result:
            (device, csd) = result
            transferred = 1 + len(device) + 1 + len(csd)
            if transferred != datalen:
                regs.carry = True
                memory.writeLongWord(address + 5, datalen - transferred)
            else:
                regs.carry = False
            data = bytearray([len(device)]) + bytearray(device) + bytearray([len(csd)]) + bytearray(csd)
            memory.writeLongWord(address + 1, dataaddr + transferred)
            memory.writeLongWord(address + 9, transferred)
            memory.writeBytes(dataaddr, data)
            handled = True
        else:
            handled = False
        return handled

    def call_get_filenames(self, op, address, regs, memory, csd):
        """
        Get filenames from the CSD, in form <length><filename>...
        """
        dataaddr = memory.readLongWord(address + 1)
        nfiles = memory.readLongWord(address + 5)
        offset = memory.readLongWord(address + 9)
        filenames = self.get_csd_filenames(offset, nfiles, regs, memory)
        if filenames is not None:
            transferred = len(filenames)
            if transferred != nfiles:
                regs.carry = True
                memory.writeLongWord(address + 5, nfiles - transferred)
            else:
                regs.carry = False
            for filename in filenames:
                data = bytearray([len(filename)]) + bytearray(filename)
                memory.writeBytes(dataaddr, data)
                dataaddr += len(data)
            memory.writeLongWord(address + 1, dataaddr)
            memory.writeLongWord(address + 9, offset + transferred)
            handled = True
        else:
            handled = False
        return handled

    def put_bytes(self, fh, data, ptr, regs, memory):
        """
        Put bytes to an open file handle.

        @param fh:      File handle to read
        @param data:    Data to write
        @param ptr:     File pointer to write at, or None to write to current pointer
        @param regs:    Registers object
        @param memory:  Memory object

        @return:        None if not handled
                        Tuple of (bytes transferred, new file pointer)
        """
        return None

    def get_bytes(self, fh, datalen, ptr, regs, memory):
        """
        Get bytes from an open file handle.

        @param fh:      File handle to read
        @param datalen: Length of data to read
        @param ptr:     File pointer to read from, or None to read from current pointer
        @param regs:    Registers object
        @param memory:  Memory object

        @return:        None if not handled
                        Tuple of (data read, new file pointer)
        """
        return None

    def get_media_title(self, regs, memory):
        """
        Get the media title and boot option

        @param regs:    Registers object
        @param memory:  Memory object

        @return:        None if not handled
                        Tuple of (media title, boot option value)
        """
        return None

    def get_csd(self, regs, memory):
        """
        Get the device name (eg "0" for disc 0) and CSD

        @param regs:    Registers object
        @param memory:  Memory object

        @return:        None if not handled
                        Tuple of (device name, CSD)
        """
        return None

    def get_lib(self, regs, memory):
        """
        Get the device name (eg "0" for disc 0) and library

        @param regs:    Registers object
        @param memory:  Memory object

        @return:        None if not handled
                        Tuple of (device name, library directory)
        """
        return None

    def get_csd_filenames(self, nfiles, offset, regs, memory):
        """
        Get filenames from the CSD.

        @param nfiles:  Maximum number of files to read
        @param offset:  Offset in directory list to start from
        @param regs:    Registers object
        @param memory:  Memory object

        @return:        None if not handled
                        List of filenames if handled
        """
        return None


class OSFSC(OSInterface):
    code = 0xFFB1
    vector = 0x021E

    def __init__(self):
        super(OSFSC, self).__init__()
        self.dispatch[0x00] = self.call_opt
        self.dispatch[0x01] = self.call_eof
        self.dispatch[0x02] = self.call_slash
        self.dispatch[0x03] = self.call_ukcommand
        self.dispatch[0x04] = self.call_run
        self.dispatch[0x05] = self.call_cat
        self.dispatch[0x06] = self.call_fs_starting
        self.dispatch[0x07] = self.call_get_handle_range
        self.dispatch[0x08] = self.call_star_command
        self.dispatch_default = self.osfsc

    def dispatch_parameters(self, regs, memory):
        """
        Decode the parameters for the address.
        """
        address = regs.x | (regs.y << 8)
        return [regs.a, address, regs, memory]

    def osfsc(self, op, address, regs, memory):
        """
        Operation codes:

        00 *OPT X, Y issued
        01 EOF checked on file handle X
        02 */<command> issued
        03 Unrecognised command issued
        04 *RUN <filename> issued
        05 *CAT <directory> issued
        06 New FS starting
        07 Get file handles range in X(low) and Y(high)
        08 *command has been issued
        """
        return False

    def call_opt(self, op, address, regs, memory):
        """
        *OPT X, Y issued
        """
        handled = self.opt(regs.x, regs.y, regs, memory)
        return handled

    def call_eof(self, op, address, regs, memory):
        """
        EOF check on a file handle.
        """
        fh = regs.x
        eof = self.eof(fh, regs, memory)
        if eof is None:
            return False
        regs.x = 0xFF if eof else 0x00
        return True

    def call_slash(self, op, address, regs, memory):
        """
        A /<command> has been issued
        """
        cli = memory.readString(address)
        # FIXME: Should we split this up?
        handled = self.slash(cli, regs, memory)
        return handled

    def call_ukcommand(self, op, address, regs, memory):
        """
        An unknown command has been issued
        """
        cli = memory.readString(address)
        # FIXME: Should we split this up?
        handled = self.ukcommand(cli, regs, memory)
        return handled

    def call_run(self, op, address, regs, memory):
        """
        *Run has been issued
        """
        cli = memory.readString(address)
        # FIXME: Should we split this up?
        handled = self.run(cli, regs, memory)
        return handled

    def call_cat(self, op, address, regs, memory):
        """
        *Cat has been issued
        """
        cat = memory.readString(address)
        handled = self.cat(cat, regs, memory)
        return handled

    def call_fs_starting(self, op, address, regs, memory):
        """
        A new FS is starting up
        """
        handled = self.fs_starting(regs, memory)
        return handled

    def call_get_handle_range(self, op, address, regs, memory):
        """
        Read the range of file handles supported.
        """
        result = self.get_handle_range(regs, memory)
        if result is None:
            return False
        (regs.x, regs.y) = result
        return True

    def call_star_command(self, op, address, regs, memory):
        """
        New *command issued (for handling *Enable)
        """
        handled = self.star_command(regs, memory)
        return handled

    def opt(self, x, y, regs, memory):
        """
        *OPT X, Y issued

        @param x, y:        Parameters to *Opt
        @param regs:        Registers object
        @param memory:      Memory object

        @return:        True if handled,
                        False if not handled
        """
        return False

    def eof(self, fh, regs, memory):
        """
        EOF#fh check

        @param fh:
        @param regs:        Registers object
        @param memory:      Memory object

        @return:        True if EOF,
                        False if not EOF,
                        None if not handled
        """
        return False

    def slash(self, cli, regs, memory):
        """
        */<command> issued.

        @param cli:         CLI to execute
        @param regs:        Registers object
        @param memory:      Memory object

        @return:        True if handled,
                        False if not handled
        """
        return False

    def ukcommand(self, cli, regs, memory):
        """
        Unknown command issued

        @param cli:         Command issued
        @param regs:        Registers object
        @param memory:      Memory object

        @return:        True if handled,
                        False if not handled
        """
        return False

    def run(self, run, regs, memory):
        """
        *Run issued.

        @param run:         Command to run
        @param regs:        Registers object
        @param memory:      Memory object

        @return:        True if handled,
                        False if not handled
        """
        return False

    def cat(self, dir, regs, memory):
        """
        *Cat issued

        @param dir:         Directory name
        @param regs:        Registers object
        @param memory:      Memory object

        @return:        True if handled,
                        False if not handled
        """
        return False

    def fs_starting(self, regs, memory):
        """
        New FS is starting.

        @param regs:        Registers object
        @param memory:      Memory object

        @return:        True if handled,
                        False if not handled
        """
        return False

    def get_handle_range(self, regs, memory):
        """
        @param regs:        Registers object
        @param memory:      Memory object

        @return:        None if not handled
                        Tuple of (low handle, high handle) if handled
        """
        return False

    def star_command(self, regs, memory):
        """
        @param regs:        Registers object
        @param memory:      Memory object

        @return:        True if handled,
                        False if not handled
        """
        return False

