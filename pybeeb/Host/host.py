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
        #print "OS_RDCH" # Could inject keypresses here maybe?
        while True:
            ch = self.console.getch()
            if ch is not None:
                break
        if ch == b'':
            raise InputEOFError("EOF received from terminal")
        return ch


class OSWORDtty(OSWORD):
    code = 0xE7EB
    vector = 0x020C

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
