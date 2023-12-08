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
        'OSRDCH'
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
        # dispatched to handle OSBYTE calls.
        # The keys in the dictionary may the value of the A register.
        # If no matching key exists, the method `osword` will be used.
        # The dispatcher used will be called with the parameters
        # `(a, address, regs, memory)`.
        self.dispatch = {
                0x00: self.osword_readline,
            }

    def call(self, regs, memory):
        dispatcher = self.dispatch.get(regs.a, None)
        if dispatcher is None:
            dispatcher = self.osword

        address = regs.x | (regs.y << 8)
        return dispatcher(regs.a, address, regs, memory)

    def osword_readline(self, a, address, regs, memory):
        # The parameter block:
        #     XY+ 0    Buffer address for input   LSB
        #         1                               MSB
        #         2    Maximum line length
        #         3    Minimum acceptable ASCII value
        #         4    Maximum acceptable ASCII value
        #
        # Only characters greater or equal to XY+3 and lesser or equal to
        # XY+4 will be accepted.
        #
        # On exit, C=0 if a carriage return terminated input.
        #          C=1 if an ESCAPE condition terminated input.
        #          Y contains line length, including carriage return if
        #          used.
        input_memory = memory.readWord(address)
        maxline = memory.readByte(address + 2)
        lowest = memory.readByte(address + 3)
        highest = memory.readByte(address + 4)

        try:
            sys.stdout.flush()
            result = self.read_line(maxline, lowest, highest)
            result = result[:maxline - 1]
            result = result + '\r'
            # FIXME: Note that the lowest and highest are not honoured by this
            regs.carry = False
            regs.Y = len(result)
            memory.writeBytes(input_memory, bytearray(result))

        except EOFError:
            raise InputEOFError("EOF received from terminal")

        except KeyboardInterrupt:
            regs.carry = True
            regs.Y = 0

        return True

    def read_line(self, maxline, lowest, highest):
        """
        Read a line of input; override with any other ReadLine implementation.
        """
        return raw_input()

    def osword(self, a, address, regs, memory):
        return False
