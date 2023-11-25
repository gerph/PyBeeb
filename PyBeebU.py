'''
Created on 12 Oct 2011

@author: chris.whitworth
'''

import sys

from PyBeebicorn import Pb, PbError, PbConstants


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


def OS_WRCH(pb, address, size, user_data): sys.stdout.write(chr(pb.reg_read(PbConstants.PB_6502_REG_A)))
def OS_RDCH(pb, address, size, user_data): print "OS_RDCH" # Could inject keypresses here maybe?

if __name__ == "__main__":
    OS_WRCH_LOC = 0xe0a4
    OS_RDCH_LOC = 0xdec5
    syscalls = { OS_WRCH_LOC : OS_WRCH,
                 OS_RDCH_LOC : OS_RDCH }
    bbc = BBC()
    bbc.go(syscalls)
