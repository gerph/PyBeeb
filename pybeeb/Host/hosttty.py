"""
Implementations of the OS interfaces which communicate with the host for input and output.
"""

import sys

from .base import OSInterface, OSWRCH, OSRDCHpostbuffer, OSWORD, OSBYTE, InputEOFError
from .console import Console


class OSWRCHtty(OSWRCH):

    def writec(self, ch):
        if ch == 127:
            sys.stdout.write('\x08 \x08')
        else:
            sys.stdout.write(chr(ch))

        # Return immediately with an RTS
        return True


class OSRDCHtty(OSRDCHpostbuffer):

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


class OSBYTEtty(OSBYTE):

    def __init__(self):
        super(OSBYTEtty, self).__init__()
        self.console = Console()

        self.dispatch[0x81] = self.inkey

    def start(self):
        self.console.terminal_init()

    def stop(self):
        self.console.terminal_reset()

    def inkey(self, a, x, y, regs, memory):
        if y == 0xFF and x == 0:
            # Read machine type
            return False
        if y == 0xFF and x >= 0x80:
            # Keyboard scan
            return False

        delay_cs = x | (y<<8)

        ch = self.console.getch(delay_cs / 100.0)

        if ch == b'':
            raise InputEOFError("EOF received from terminal")

        if ch is not None:
            # If a character is detected, X=ASCII value of key pressed, Y=0 and C=0.
            regs.x = ord(ch)
            regs.y = 0
            regs.carry = False
        else:
            # If a character is not detected within timeout then Y=&FF and C=1.
            regs.y = 0xff
            regs.carry = False
        if ch == b'\x1b':
            # If Escape is pressed then Y=&1B (27) and C=1.
            regs.carry = True

        return True


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
            regs.y = len(result)
            memory.writeBytes(input_memory, bytearray(result.encode('latin-1')))

        except EOFError:
            raise InputEOFError("EOF received from terminal")

        except KeyboardInterrupt:
            regs.carry = True
            regs.y = 0

        return True

    def read_line(self, maxline, lowest, highest):
        """
        Read a line of input; override with any other ReadLine implementation.
        """

        console_active = self.console.terminal_active
        if console_active:
            self.console.terminal_reset()

        try:
            if sys.version_info.major == 2:
                result = raw_input()
            else:
                result = input()
        finally:
            if console_active:
                self.console.terminal_init()

        return result
