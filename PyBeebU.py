#!/usr/bin/env python
'''
Created on 12 Oct 2011

@author: chris.whitworth
'''

import sys

from pybeeb.PyBeebicorn import Pb, PbError, PbConstants
from console import Console


class BBC(object):
    def __init__(self, pcTrace = False, verbose = False):
        self.pb = Pb()

    def go(self, syscalls):
        try:
            # Register the syscall execution entry points
            hooks = []
            for addr, func in syscalls.items():
                hooks.append(self.pb.hook_add(PbConstants.PB_HOOK_CODE,
                                              func, begin=addr, end=addr + 1))

            self.pb.emu_start(self.pb.reg_read(PbConstants.PB_6502_REG_PC), -1)
        finally:
            # Deregister the entry points
            for hook in hooks:
                self.pb.hook_del(hook)


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
        if regs.a == 127:
            sys.stdout.write('\x08 \x08')
        else:
            sys.stdout.write(chr(regs.a))

        # Return immediately with an RTS
        return True


class OSRDCH(OSInterface):
    code = 0xDEC5
    vector = 0x0210

    def __init__(self):
        super(OSRDCH, self).__init__()
        self.console = Console()

    def start(self):
        self.console.terminal_init()

    def stop(self):
        self.console.terminal_reset()

    def call(self, regs, memory):
        # See: https://mdfs.net/Docs/Comp/BBC/OS1-20/DC1C
        #print "OS_RDCH" # Could inject keypresses here maybe?
        while True:
            ch = self.console.getch()
            if ch is not None:
                break
        if ch == b'':
            raise Exception("EOF")
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
        if command == 'QUIT':
            sys.exit()
        return False


def main():

    def trace(pb, address, size, user_data):
        data = pb.mem_read(address, size)
        execcode = ' '.join('%02X' % (b,) for b in data)

        (inst, formatted, params, comment) = pb.dis.disassemble(address)
        print("&%04X: %-10s : %s %s" % (address, execcode, inst, formatted))

    def mem_hook(pb, access, address, size, value, user_data):
        print("Access %s of &%04x, size %-3i from &%04x" % ('READ' if access == PbConstants.PB_MEM_READ else 'WRITE',
                                                            address, size,
                                                            pb.reg_read(PbConstants.PB_6502_REG_PC)))

    bbc = BBC()

    # Trace all the ROM execution
    #bbc.pb.hook_add(PbConstants.PB_HOOK_CODE, trace, begin=0x8000, end=0xC000)

    # Report memory reads and writes around PAGE
    #bbc.pb.hook_add(PbConstants.PB_HOOK_MEM_READ | PbConstants.PB_HOOK_MEM_WRITE, mem_hook, begin=0xe00, end=0xe01)

    # Report memory reads and writes anywhere between the PAGE and HIMEM (video memory).
    #bbc.pb.hook_add(PbConstants.PB_HOOK_MEM_READ | PbConstants.PB_HOOK_MEM_WRITE, mem_hook, begin=0xe00, end=0x7c00)

    interface_classes = (
            OSWRCH,
            OSRDCH,
            OSCLI
        )
    try:
        syscalls = {}
        interfaces = []
        for cls in interface_classes:
            interface = cls()
            interface.start()
            interfaces.append(interface)
            def hook(pb, address, size, user_data, interface=interface):
                handled = interface.call(pb.reg, pb.memory)
                if handled:
                    pb.reg.pc = pb.dispatch.pullWord() + 1

            syscalls[interface.code] = hook

        bbc.go(syscalls)
    except Exception as exc:
        if str(exc) == 'EOF':
            print("\nEOF")
        else:
            raise
    finally:
        for interfaces in reversed(interfaces):
            interface.stop()


if __name__ == "__main__":
    main()
