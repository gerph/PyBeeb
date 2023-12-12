#!/usr/bin/env python
'''
Created on 12 Oct 2011
Updated on 09 Dec 2023

@author: chris.whitworth, gerph
'''

import sys

from pybeeb.PyBeebicorn import Pb, PbError, PbConstants
from pybeeb.Host import (BBCError, InputEOFError, OSInterface,
                         OSCLI, OSBYTE, OSFILE, OSFIND, OSARGS, OSBPUT, OSBGET, OSGBPB, OSFSC)
from pybeeb.Host.host import OSWRCHtty, OSRDCHtty, OSWORDtty


class BBC(object):
    def __init__(self, pcTrace=False, verbose=False):
        self.pb = Pb()

    def go(self, syscalls):
        try:
            # Register the syscall execution entry points
            hooks = []
            for addr, func in syscalls.items():
                hooks.append(self.pb.hook_add(PbConstants.PB_HOOK_CODE,
                                              func, begin=addr, end=addr + 1))

            self.pb.emu_start(self.pb.reg_read(PbConstants.PB_6502_REG_PC), -2)
        finally:
            # Deregister the entry points
            for hook in hooks:
                self.pb.hook_del(hook)


class OSCLIquit(OSCLI):

    def command(self, command, args):
        if command == b'QUIT':
            sys.exit()
        return False


class OSBYTEversion(OSBYTE):

    def __init__(self):
        super(OSBYTEversion, self).__init__()

        self.dispatch[(0x00, 0x00)] = self.osbyte_osversion_error

    def osbyte_osversion_error(self, a, x, y, regs, memory):
        raise BBCError(247, "OS 1.20 (PyBeeb)")


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
            OSWRCHtty,
            OSRDCHtty,
            OSCLIquit,
            OSBYTEversion,
            OSWORDtty,
            OSFILE,
            OSFIND,
            OSARGS,
            OSBPUT,
            OSBGET,
            OSGBPB,
            OSFSC
        )
    try:
        syscalls = {}
        interfaces = []
        for cls in interface_classes:
            interface = cls()
            interface.start()
            interfaces.append(interface)
            def hook(pb, address, size, user_data, interface=interface):
                try:
                    handled = interface.call(pb.reg, pb.memory)
                    if handled:
                        pb.reg.pc = pb.dispatch.pullWord() + 1
                except BBCError as exc:
                    pb.memory.writeBytes(0x100, bytearray([0, exc.errnum]))
                    pb.memory.writeBytes(0x100 + 2, bytearray(exc.errmess.encode('latin-1')))
                    pb.reg.pc = 0x100

            syscalls[interface.code] = hook

        bbc.go(syscalls)

    except InputEOFError as exc:
        print("\nEOF")

    finally:
        for interfaces in reversed(interfaces):
            interface.stop()


if __name__ == "__main__":
    main()
