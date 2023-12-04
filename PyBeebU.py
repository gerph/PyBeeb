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


if __name__ == "__main__":
    OS_WRCH_LOC = 0xe0a4
    OS_RDCH_LOC = 0xdec5

    console = Console()

    def OS_WRCH(pb, address, size, user_data):
        c = pb.reg_read(PbConstants.PB_6502_REG_A)
        if c == 127:
            sys.stdout.write('\x08 \x08')
        else:
            sys.stdout.write(chr(c))

    def OS_RDCH(pb, address, size, user_data):
        # See: https://mdfs.net/Docs/Comp/BBC/OS1-20/DC1C
        #print "OS_RDCH" # Could inject keypresses here maybe?
        while True:
            ch = console.getch()
            if ch is not None:
                break
        if ch == b'':
            raise Exception("EOF")
        ch = ord(ch)
        ps = pb.reg_read(PbConstants.PB_6502_REG_PS)
        if ch == 27:
            ps |= PbConstants.PB_6502_FLAG_CARRY

            # Bit of a hack as we don't have interrupts
            # Set the escape flag
            pb.mem_write(0xFF, bytearray([0x80]))
        else:
            ps &= ~PbConstants.PB_6502_FLAG_CARRY
        pb.reg_write(PbConstants.PB_6502_REG_PS, ps)
        pb.reg_write(PbConstants.PB_6502_REG_A, ch)
        pb.reg_write(PbConstants.PB_6502_REG_PC, 0xDF0B)  # RTS instruction

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

    syscalls = { OS_WRCH_LOC : OS_WRCH,
                 OS_RDCH_LOC : OS_RDCH }
    try:
        console.terminal_init()
        bbc.go(syscalls)
    except Exception as exc:
        if str(exc) == 'EOF':
            print("\nEOF")
        else:
            raise
    finally:
        console.terminal_reset()
