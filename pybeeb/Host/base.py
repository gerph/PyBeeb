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
        if isinstance(errmess, bytes):
            self.errmess = errmess.decode('latin-1')
        else:
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
        #   (A, X, Y, pb)
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

    def dispatch_parameters(self, pb):
        """
        Prepare a set of parameters to pass to the dispatcher.

        @param pb:  Emulator object, containing `regs` and `memory`

        @return:    list of parameters to pass to the dispatcher
        """
        return [pb.regs.a, pb.regs.x, pb.regs.y, pb]

    def call(self, pb):
        """
        Call the interface with a given set of parameters.

        The Registers and Memory will be updated on return.

        May raise exception BBCError to indicate that an error should be reported.

        @param pb:  Emulator object, containing `regs` and `memory`

        @return:    True if the call has been handled (return from interface),
                    False if call should continue at the code execution point
        """
        dispatcher = self.dispatch.get((pb.regs.a, pb.regs.x, pb.regs.y), None)
        if dispatcher is None:
            dispatcher = self.dispatch.get((pb.regs.a, pb.regs.x), None)
            if dispatcher is None:
                dispatcher = self.dispatch.get(pb.regs.a, None)
                if dispatcher is None:
                    dispatcher = self.dispatch_default
        if dispatcher:
            params = self.dispatch_parameters(pb)
            return dispatcher(*params)
        return False


class OSWRCH(OSInterface):
    code = 0xE0A4
    vector = 0x020E

    def call(self, pb):
        return self.writec(pb.regs.a)

    def writec(self, ch):
        """
        Write a BBC VDU code to the output stream.
        """
        return False


class OSRDCH(OSInterface):
    """
    OSRDCH entry at the top of the routine.
    """
    code = 0xDEC5
    vector = 0x0210

    def call(self, pb):
        try:
            ch = self.readc()
            if ch is None:
                return False
            ch = ord(ch)

        except KeyboardInterrupt:
            ch = 27

        if ch == 27:
            pb.regs.carry = True

            # Bit of a hack as we don't have interrupts
            # Set the escape flag
            pb.memory.writeByte(0xFF, 0x80)
        else:
            pb.regs.carry = False
        pb.regs.a = ch

        # Return immediately with an RTS
        return True

    def readc(self):
        return None


class OSRDCHpostbuffer(OSInterface):
    """
    OSRDCH, but only after the buffer has been read.

    Handling this entry after the buffer has been read allows *EXEC and insertions through *Key and *FX138.

    =>  C = 0 if character already returned from buffer.
        C = 1 if no character was read, in A
    """
    code = 0xDEF0
    vector = None

    def call(self, pb):
        if not pb.regs.carry:
            # A character was already read
            return False

        try:
            ch = self.readc()
            if ch is None:
                return False
            ch = ord(ch)

        except KeyboardInterrupt:
            ch = 27

        if ch == 27:
            # Bit of a hack as we don't have interrupts
            # Set the escape flag
            pb.memory.writeByte(0xFF, 0x80)

        pb.regs.carry = False
        pb.regs.a = ch

        # The state we've just updated with will cause us to return the character
        return False

    def readc(self):
        return None


class OSCLI(OSInterface):
    code = 0xDF89
    vector = 0x0208

    def __init__(self):
        super(OSCLI, self).__init__()

        # The command dispatch table can be used to make it easier
        # to handle individual commands. The key is an upper case
        # command name, and the value is a method which should be
        # called to handle it. The method will be called as:
        #   method(args, pb)
        self.commands_dispatch = {}

    def call(self, pb):
        xy = pb.regs.x | (pb.regs.y << 8)
        cli = pb.memory.readString(xy)
        while cli[0:1] in (b'*', b' '):
            cli = cli[1:]

        cmd = bytearray()
        args = ''
        abbrev = False
        for index, c in enumerate(bytearray(cli)):
            #print("cli = %r, c = %r" % (cli, c))
            if c == 32:
                args = cli[index + 1:]
                break
            if c == ord('.'):
                args = cli[index + 1:]
                abbrev = True
                break
            cmd.append(c)

        dispatch = None
        command = bytes(cmd).upper()
        #print("CMD: %r (abbrev=%s), args: %r" % (command, abbrev, args))
        if abbrev:
            if not command:
                # Always give up on the `*.` command, so that it's
                # passed on to the OS to be handled as *CAT through
                # OSFSC.
                return False
            for key, func in self.commands_dispatch.items():
                if key.startswith(command):
                    dispatch = func
        else:
            dispatch = self.commands_dispatch.get(command, None)
        if dispatch:
            return dispatch(args, pb)

        return self.command(command, args, pb)

    def command(self, command, args, pb):
        return False


class OSBYTE(OSInterface):
    code = 0xE772
    vector = 0x020A

    def __init__(self):
        super(OSBYTE, self).__init__()
        self.dispatch_default = self.osbyte

    def osbyte(self, a, x, y, pb):
        #print("OSByte &%02x, %i, %i" % (a, x, y))
        return False


class OSWORD(OSInterface):
    code = 0xE7EB
    vector = 0x020C

    def __init__(self):
        super(OSWORD, self).__init__()

        # The dispatcher used will be called with the parameters
        #   (a, address, pb)
        self.dispatch_default = self.osword

    def dispatch_parameters(self, pb):
        """
        Decode the parameters for the address.
        """
        address = pb.regs.x | (pb.regs.y << 8)
        return [pb.regs.a, address, pb]

    def osword(self, a, address, pb):
        return False


class OSFILE(OSInterface):
    code = 0xF27D
    vector = 0x0212

    def __init__(self):
        super(OSFILE, self).__init__()

        # The default dispatcher is called with:
        #   (op, filename, address, pb)
        self.dispatch_default = self.osfile

    def dispatch_parameters(self, pb):
        address = pb.regs.x | (pb.regs.y << 8)
        filename_ptr = pb.memory.readWord(address)
        filename = pb.memory.readString(filename_ptr)
        return [pb.regs.a, filename, address, pb]

    def osfile(self, op, filename, address, pb):
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
        @param pb:  Emulator object, containing `regs` and `memory`

        @return:        True if handled
                        False if not handled
        """
        handled = False

        if op == 0:
            # Save
            src_address = pb.memory.readLongWord(address + 10)
            src_length = pb.memory.readLongWord(address + 14) - src_address
            info_load = pb.memory.readLongWord(address + 2)
            info_exec = pb.memory.readLongWord(address + 6)
            handled = self.save(filename, src_address, src_length, info_load, info_exec, pb)

        elif op == 1:
            # Write load+exec+attr
            info_load = pb.memory.readLongWord(address + 2)
            info_exec = pb.memory.readLongWord(address + 6)
            info_attr = pb.memory.readLongWord(address + 14)
            handled = self.write_info(filename, info_load, info_exec, info_attr, pb)

        elif op == 2:
            # Write load
            info_load = pb.memory.readLongWord(address + 2)
            handled = self.write_load(filename, info_load, pb)

        elif op == 3:
            # Write exec
            info_exec = pb.memory.readLongWord(address + 6)
            handled = self.write_exec(filename, info_exec, pb)

        elif op == 4:
            # Write attr
            info_attr = pb.memory.readLongWord(address + 14)
            handled = self.write_attr(filename, info_attr, pb)

        elif op == 5:
            # Read load+exec+attr
            result = self.read_info(filename, pb)
            if result:
                handled = True
                (info_type, info_load, info_exec, info_length, info_attr) = result
                pb.memory.writeLongWord(address + 2, info_load)
                pb.memory.writeLongWord(address + 6, info_exec)
                pb.memory.writeLongWord(address + 10, info_length)
                pb.memory.writeLongWord(address + 14, info_attr)
                pb.regs.a = info_type
            else:
                handled = False

        elif op == 6:
            # Delete
            handled = self.delete(filename, pb)

        elif op == 255:
            # Load
            if pb.memory.readByte(address + 6) == 0:
                load_address = pb.memory.readLongWord(address + 2)
            else:
                load_address = None
            result = self.load(filename, load_address, pb)
            if result:
                handled = True
                (info_type, info_load, info_exec, info_length, info_attr) = result
                pb.memory.writeLongWord(address + 2, info_load)
                pb.memory.writeLongWord(address + 6, info_exec)
                pb.memory.writeLongWord(address + 10, info_length)
                pb.memory.writeLongWord(address + 14, info_attr)
                pb.regs.a = info_type
            else:
                handled = False

        return handled

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
        return False

    def write_info(self, filename, info_load, info_exec, info_attr, pb):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param info_exec:   Exec address
        @param info_attr:   File attributes
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

    def write_load(self, filename, info_load, pb):
        """
        @param filename:    File to operate on
        @param info_load:   Load address
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

    def write_exec(self, filename, info_exec, pb):
        """
        @param filename:    File to operate on
        @param info_exec:   Exec address
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

    def write_attr(self, filename, info_attr, pb):
        """
        @param filename:    File to operate on
        @param info_attr:   File attributes
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

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
        return None

    def delete(self, filename, pb):
        """
        @param filename:    File to operate on
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    True if the call is handled, or False if it's not handled
        """
        return False

    def load(self, filename, load_address, pb):
        """
        @param filename:    File to operate on
        @param pb:          Emulator object, containing `regs` and `memory`

        @return:    None if not handled,
                    Tuple of (info_type, info_load, info_exec, info_length, info_attr) if handled
        """
        return None


class OSARGS(OSInterface):
    code = 0xF18E
    vector = 0x0214

    def call(self, pb):
        # NOTE: We do not use the standard dispatcher mechanism here
        #       because the primary discriminator is the Y register,
        #       rather than the A register.
        dispatcher = self.dispatch.get((pb.regs.a, pb.regs.y), None)
        if dispatcher is None:
            dispatcher = self.dispatch.get(pb.regs.a, None)
            if dispatcher is None:
                dispatcher = self.osargs

        fh = pb.regs.y
        address = pb.regs.x
        return dispatcher(pb.regs.a, fh, address, pb)

    def osargs(self, op, fh, address, pb):
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
        #print("OSArgs: fh=%i, addr=%x" % (fh, address))
        if fh == 0:
            # Filehandle = 0
            if op == 0x00:
                result = self.read_current_filesystem(pb)
                handled = result is not None
                if handled:
                    pb.regs.a = result

            elif op == 0x01:
                # Read CLI args
                result = self.read_cli_args(pb)
                handled = result is not None
                if handled:
                    pb.memory.writeLongWord(address, result)

            elif op == 0xFF:
                # Flush all files
                handled = self.flush_all_files(pb)

        else:
            # Filehandle supplied
            if op == 0x00:
                # Read PTR#
                result = self.read_ptr(fh, pb)
                handled = result is not None
                if handled:
                    pb.memory.writeLongWord(address, result)

            elif op == 0x01:
                # Write PTR#
                ptr = pb.memory.readLongWord(address)
                handled = self.write_ptr(fh, ptr, pb)

            elif op == 0x02:
                # Read EXT#
                result = self.read_ext(fh, pb)
                handled = result is not None
                if handled:
                    pb.memory.writeLongWord(address, result)

            elif op == 0xFF:
                # Flush file to storage
                handled = self.flush_file(fh, pb)

        return False

    def read_ptr(self, fh, pb):
        """
        Read PTR#.

        @param fh:      File handle to read
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    PTR for the file, or None if not handled
        """
        return None

    def read_ext(self, fh, pb):
        """
        Read EXT#.

        @param fh:      File handle to read
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    EXT for the file, or None if not handled
        """
        return None

    def write_ptr(self, fh, ptr, pb):
        """
        Write PTR#.

        @param fh:      File handle to read
        @param ptr:     New PTR value
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    True if handled, False if not handled
        """
        return None

    def flush_file(self, fh, pb):
        """
        Flush file to storage.

        @param fh:      File handle to read
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    True if handled, False if not handled
        """
        return False

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
        return None

    def read_cli_args(self, pb):
        """
        Read the CLI arguments.

        @param pb:      Emulator object, containing `regs` and `memory`

        @return:    Address of CLI arguments, or None is not handled
        """
        return None


class OSBGET(OSInterface):
    code = 0xF4C9
    vector = 0x0216

    def call(self, pb):
        fh = pb.regs.y
        b = self.osbget(fh, pb)
        if b is None:
            return False

        if b == -1:
            pb.regs.carry = True
        else:
            pb.regs.carry = False
            pb.regs.a = b
        return True

    def osbget(self, fh, pb):
        """
        Handle BGET, returning the byte read.

        @param fh:  File handle to read
        @param pb:  Emulator object, containing `regs` and `memory`

        @return:    byte read, -1 if at file end, or None if not handled
        """
        return None


class OSBPUT(OSInterface):
    code = 0xF529
    vector = 0x0218

    def call(self, pb):
        fh = pb.regs.y
        b = pb.regs.a
        handled = self.osbput(b, fh, pb)
        return handled

    def osbput(self, b, fh, pb):
        """
        Handle BPUT, writing the supplied byte to a file..

        @param fh:  File handle to write to
        @param b:   Byte to write
        @param pb:  Emulator object, containing `regs` and `memory`

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

    def call_close(self, a, x, y, pb):
        return self.close(fh=y, pb=pb)

    def call_open(self, a, x, y, pb):
        filename_ptr = x | (y << 8)
        filename = pb.memory.readString(filename_ptr)
        fh = self.open(a, filename, pb)
        if fh is None:
            return False
        pb.regs.a = fh
        return True

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
        return None

    def close(self, fh, pb):
        """
        Close a previously open file.

        @param fh:  file handle to close, or 0 to close all files.
        @param pb:  Emulator object, containing `regs` and `memory`

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
        self.dispatch[0x06] = lambda op, address, pb: self.call_get_csd_lib(op, address, pb, csd=True)
        self.dispatch[0x07] = lambda op, address, pb: self.call_get_csd_lib(op, address, pb, csd=False)
        self.dispatch[0x08] = self.call_get_filenames
        self.dispatch_default = self.osgbpb

    def dispatch_parameters(self, pb):
        """
        Decode the parameters for the address.
        """
        address = pb.regs.x | (pb.regs.y << 8)
        return [pb.regs.a, address, pb]

    def osgbpb(self, op, address, pb):
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

    def call_put_bytes(self, op, address, pb):
        """
        Put bytes (at a given location).
        """
        fh = pb.memory.readByte(address)
        dataaddr = pb.memory.readLongWord(address + 1)
        datalen = pb.memory.readLongWord(address + 5)
        if op == 1:
            ptr = pb.memory.readLongWord(address + 9)
        else:
            ptr = None
        data = pb.memory.readBytes(dataaddr, datalen)
        result = self.put_bytes(fh, data, ptr, pb)
        if result:
            (transferred, newptr) = result
            if transferred != datalen:
                pb.regs.carry = True
                pb.memory.writeLongWord(address + 5, datalen - transferred)
            else:
                pb.regs.carry = False
            pb.memory.writeLongWord(address + 1, dataaddr + transferred)
            pb.memory.writeLongWord(address + 9, newptr)
            handled = True
        else:
            handled = False
        return handled

    def call_get_bytes(self, op, address, pb):
        """
        Put bytes (at a given location).
        """
        fh = pb.memory.readByte(address)
        dataaddr = pb.memory.readLongWord(address + 1)
        datalen = pb.memory.readLongWord(address + 5)
        if op == 1:
            ptr = pb.memory.readLongWord(address + 9)
        else:
            ptr = None
        result = self.get_bytes(fh, datalen, ptr, pb)
        if result:
            (data, newptr) = result
            transferred = len(data)
            if transferred != datalen:
                pb.regs.carry = True
                pb.memory.writeLongWord(address + 5, datalen - transferred)
            else:
                pb.regs.carry = False
            pb.memory.writeLongWord(address + 1, dataaddr + transferred)
            pb.memory.writeLongWord(address + 9, newptr)
            pb.memory.writeBytes(dataaddr, data)
            handled = True
        else:
            handled = False
        return handled

    def call_get_media_title(self, op, address, pb):
        """
        Get media title and option as <len><title><option>
        """
        dataaddr = pb.memory.readLongWord(address + 1)
        datalen = pb.memory.readLongWord(address + 5)
        result = self.get_media_title(pb)
        if result:
            (title, option) = result
            transferred = 1 + len(title) + 1
            if transferred != datalen:
                pb.regs.carry = True
                pb.memory.writeLongWord(address + 5, datalen - transferred)
            else:
                pb.regs.carry = False
            data = bytearray([len(title)]) + bytearray(title) + bytearray(option)
            pb.memory.writeLongWord(address + 1, dataaddr + transferred)
            pb.memory.writeLongWord(address + 9, transferred)
            pb.memory.writeBytes(dataaddr, data)
            handled = True
        else:
            handled = False
        return handled

    def call_get_csd_lib(self, op, address, pb, csd):
        """
        Get CSD/library and device as <len><device><len><csd>
        """
        dataaddr = pb.memory.readLongWord(address + 1)
        datalen = pb.memory.readLongWord(address + 5)
        if csd:
            result = self.get_csd(pb)
        else:
            result = self.get_lib(pb)
        if result:
            (device, csd) = result
            transferred = 1 + len(device) + 1 + len(csd)
            if transferred != datalen:
                pb.regs.carry = True
                pb.memory.writeLongWord(address + 5, datalen - transferred)
            else:
                pb.regs.carry = False
            data = bytearray([len(device)]) + bytearray(device) + bytearray([len(csd)]) + bytearray(csd)
            pb.memory.writeLongWord(address + 1, dataaddr + transferred)
            pb.memory.writeLongWord(address + 9, transferred)
            pb.memory.writeBytes(dataaddr, data)
            handled = True
        else:
            handled = False
        return handled

    def call_get_filenames(self, op, address, pb, csd):
        """
        Get filenames from the CSD, in form <length><filename>...
        """
        dataaddr = pb.memory.readLongWord(address + 1)
        nfiles = pb.memory.readLongWord(address + 5)
        offset = pb.memory.readLongWord(address + 9)
        filenames = self.get_csd_filenames(offset, nfiles, pb)
        if filenames is not None:
            transferred = len(filenames)
            if transferred != nfiles:
                pb.regs.carry = True
                pb.memory.writeLongWord(address + 5, nfiles - transferred)
            else:
                pb.regs.carry = False
            for filename in filenames:
                data = bytearray([len(filename)]) + bytearray(filename)
                pb.memory.writeBytes(dataaddr, data)
                dataaddr += len(data)
            pb.memory.writeLongWord(address + 1, dataaddr)
            pb.memory.writeLongWord(address + 9, offset + transferred)
            handled = True
        else:
            handled = False
        return handled

    def put_bytes(self, fh, data, ptr, pb):
        """
        Put bytes to an open file handle.

        @param fh:      File handle to read
        @param data:    Data to write
        @param ptr:     File pointer to write at, or None to write to current pointer
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        None if not handled
                        Tuple of (bytes transferred, new file pointer)
        """
        return None

    def get_bytes(self, fh, datalen, ptr, pb):
        """
        Get bytes from an open file handle.

        @param fh:      File handle to read
        @param datalen: Length of data to read
        @param ptr:     File pointer to read from, or None to read from current pointer
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        None if not handled
                        Tuple of (data read, new file pointer)
        """
        return None

    def get_media_title(self, pb):
        """
        Get the media title and boot option

        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        None if not handled
                        Tuple of (media title, boot option value)
        """
        return None

    def get_csd(self, pb):
        """
        Get the device name (eg "0" for disc 0) and CSD

        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        None if not handled
                        Tuple of (device name, CSD)
        """
        return None

    def get_lib(self, pb):
        """
        Get the device name (eg "0" for disc 0) and library

        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        None if not handled
                        Tuple of (device name, library directory)
        """
        return None

    def get_csd_filenames(self, nfiles, offset, pb):
        """
        Get filenames from the CSD.

        @param nfiles:  Maximum number of files to read
        @param offset:  Offset in directory list to start from
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        None if not handled
                        List of filenames if handled
        """
        return None


class OSFSC(OSInterface):
    code = 0xF1B1
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

    def dispatch_parameters(self, pb):
        """
        Decode the parameters for the address.
        """
        address = pb.regs.x | (pb.regs.y << 8)
        return [pb.regs.a, address, pb]

    def osfsc(self, op, address, pb):
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

    def call_opt(self, op, address, pb):
        """
        *OPT X, Y issued
        """
        handled = self.opt(pb.regs.x, pb.regs.y, pb)
        return handled

    def call_eof(self, op, address, pb):
        """
        EOF check on a file handle.
        """
        fh = pb.regs.x
        eof = self.eof(fh, pb)
        if eof is None:
            return False
        pb.regs.x = 0xFF if eof else 0x00
        return True

    def call_slash(self, op, address, pb):
        """
        A /<command> has been issued
        """
        cli = pb.memory.readString(address)
        # FIXME: Should we split this up?
        handled = self.slash(cli, pb)
        return handled

    def call_ukcommand(self, op, address, pb):
        """
        An unknown command has been issued
        """
        cli = pb.memory.readString(address)
        # FIXME: Should we split this up?
        handled = self.ukcommand(cli, pb)
        return handled

    def call_run(self, op, address, pb):
        """
        *Run has been issued
        """
        cli = pb.memory.readString(address)
        # FIXME: Should we split this up?
        handled = self.run(cli, pb)
        return handled

    def call_cat(self, op, address, pb):
        """
        *Cat has been issued
        """
        path = pb.memory.readString(address)
        handled = self.cat(path, pb)
        return handled

    def call_fs_starting(self, op, address, pb):
        """
        A new FS is starting up
        """
        handled = self.fs_starting(pb)
        return handled

    def call_get_handle_range(self, op, address, pb):
        """
        Read the range of file handles supported.
        """
        result = self.get_handle_range(pb)
        if result is None:
            return False
        (pb.regs.x, pb.regs.y) = result
        return True

    def call_star_command(self, op, address, pb):
        """
        New *command issued (for handling *Enable)
        """
        handled = self.star_command(pb)
        return handled

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

        @param fh:      File handle to check
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if EOF,
                        False if not EOF,
                        None if not handled
        """
        return False

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

    def cat(self, dir, pb):
        """
        *Cat issued

        @param dir:     Directory name
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        return False

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
        return False

    def star_command(self, pb):
        """
        @param pb:      Emulator object, containing `regs` and `memory`

        @return:        True if handled,
                        False if not handled
        """
        return False
