"""
Implementations of the OS interfaces which communicate with the host.
"""

import sys

from .base import OSInterface, OSWRCH, OSRDCH, OSWORD, InputEOFError
from .console import Console


class OSWRCHtty(OSWRCH):

    def writec(self, ch):
        if ch == 127:
            sys.stdout.write('\x08 \x08')
        else:
            sys.stdout.write(chr(ch))

        # Return immediately with an RTS
        return True


class OSRDCHtty(OSRDCH):

    def __init__(self):
        super(OSRDCHtty, self).__init__()
        self.console = Console()

    def start(self):
        self.console.terminal_init()

    def stop(self):
        self.console.terminal_reset()

    def readc(self):
        # See: https://mdfs.net/Docs/Comp/BBC/OS1-20/DC1C
        while True:
            ch = self.console.getch()
            if ch is not None:
                break
        if ch == b'':
            raise InputEOFError("EOF received from terminal")
        return ch


class OSWORDtty(OSWORD):

    def __init__(self):
        super(OSWORDtty, self).__init__()
        self.console = Console()

        # The dispatch dictionary contains the functions that should be
        # dispatched to handle OSBYTE calls.
        # The keys in the dictionary may the value of the A register.
        # If no matching key exists, the method `osword` will be used.
        # The dispatcher used will be called with the parameters
        # `(a, address, regs, memory)`.
        self.dispatch[0x00] = self.osword_readline

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

        console_active = self.console.terminal_active
        if console_active:
            self.console.terminal_reset()

        try:
            result = raw_input()
        finally:
            if console_active:
                self.console.terminal_init()

        return result
