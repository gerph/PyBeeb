"""
Unicorn-like interface for PyBeeb.

Allows code that was written for Unicorn to work with PyBeeb with minimal
modifications (or just reamapping the variable names).
"""

import os.path

from .CPU import Memory as Memory
from .CPU import Registers as Registers
from .CPU import AddressDispatcher as AddressDispatcher
from .CPU import Writeback as Writeback
from .CPU import ExecutionUnit as ExecutionUnit
from .CPU import Dispatch as Dispatch
from .CPU import InstructionDecoder as Decoder
from . import BBCMicro
from .BBCMicro import System as BBCMicroSystem


class PbConstants(object):
    PB_6502_REG_INVALID = 0
    PB_6502_REG_PC = 1
    PB_6502_REG_SP = 2
    PB_6502_REG_A = 3
    PB_6502_REG_X = 4
    PB_6502_REG_Y = 5
    PB_6502_REG_PS = 6

    PB_6502_FLAG_CARRY = (1<<0)
    PB_6502_FLAG_ZERO = (1<<1)
    PB_6502_FLAG_INTDISBLE = (1<<2)
    PB_6502_FLAG_DECIMAL = (1<<3)
    PB_6502_FLAG_BRK = (1<<4)
    PB_6502_FLAG_UNUSED = (1<<5)
    PB_6502_FLAG_OVERFLOW = (1<<6)
    PB_6502_FLAG_NEGATIVE = (1<<7)

    PB_ERR_OK = 0
    PB_ERR_INSN_INVALID = 10
    PB_ERR_ARG = 15

    PB_MEM_READ = 16
    PB_MEM_WRITE = 17
    PB_HOOK_CODE = 4
    PB_HOOK_MEM_READ = 1024
    PB_HOOK_MEM_WRITE = 2048


# access to error code via @errno of UcError
class PbError(Exception):
    def __init__(self, errno):
        self.errno = errno

    def __str__(self):
        return "Error %s" % (self.errno,)


def pb_version():
    major = 0
    minor = 0
    combined = (major<<8) | minor
    return (major, minor, combined)


class PbHook(object):

    def __init__(self, pb, htype, callback, user_data=None, begin=1, end=0):
        self.pb = pb
        self.htype = htype
        self.callback = callback
        self.user_data = user_data
        self.address = begin
        self.end = end

    def __contains__(self, value):
        return value >= self.address and value < self.end

    def call(self, *args):
        args = list(args)
        args.append(self.user_data)
        self.callback(self.pb, *args)


class PbDispatcher(Dispatch.Dispatcher):
    """
    Dispatcher which handles execution hooks.
    """
    def __init__(self, pb, decoder, addressDispatcher, executionDispatcher, writebackDispatcher, memory, registers):
        super(PbDispatcher, self).__init__(decoder, addressDispatcher, executionDispatcher, writebackDispatcher,
                                           memory, registers)
        self.pb = pb

        # Execution hooks - when we hit an address in the range we call the hook
        self.hook_exec = []

    def hook_add(self, hook):
        self.hook_exec.append(hook)

    def hook_del(self, hook):
        self.hook_exec.remove(hook)

    def execute(self, pc, length, opcode, instruction, writeback):
        for hook in self.hook_exec:
            if pc in hook:
                hook.call(pc, length)
                if pc != self.pb.reg.pc:
                    # They changed the execution location, so we're not running this instruction any more.
                    return self.pb.reg.pc

        if self.pb.executing:
            return super(PbDispatcher, self).execute(pc, length, opcode, instruction, writeback)


class Pb(object):
    insts_filename = os.path.join(os.path.dirname(__file__), 'insts.csv')

    def __init__(self):
        # We only support 6502, so there is no architecture or mode flag.
        self.memory = Memory.Memory()
        self.reg = Registers.RegisterBank()
        addrDispatch = AddressDispatcher.AddressDispatcher(self.memory, self.reg)

        execDispatch = ExecutionUnit.ExecutionDispatcher(self.memory,self.reg)
        writebackDispatch = Writeback.Dispatcher(self.memory,self.reg)

        decoder = Decoder.Decoder(self.insts_filename)

        self.dispatch = PbDispatcher(self, decoder, addrDispatch,
                                     execDispatch, writebackDispatch,
                                     self.memory, self.reg)

        self.bbc = BBCMicro.System.Beeb(self.dispatch)

        self.executing = False

        def write_pc(v):
            #print("Set PC to &%04x" % (v,))
            self.reg.pc = v & 0xFFFF

        def write_sp(v):
            self.reg.sp = v & 0xFF

        def write_a(v):
            self.reg.a = v & 0xFF

        def write_x(v):
            self.reg.x = v & 0xFF

        def write_y(v):
            self.reg.y = v & 0xFF

        self.reg_dispatch = {
                PbConstants.PB_6502_REG_PC: (lambda: self.reg.pc, write_pc),
                PbConstants.PB_6502_REG_SP: (lambda: self.reg.sp, write_sp),
                PbConstants.PB_6502_REG_A: (lambda: self.reg.a, write_a),
                PbConstants.PB_6502_REG_X: (lambda: self.reg.x, write_x),
                PbConstants.PB_6502_REG_Y: (lambda: self.reg.y, write_y),
                PbConstants.PB_6502_REG_PS: (lambda: self.reg.ps(), lambda v: self.reg.setPS(v)),
            }

    # emulate from @begin, and stop when reaching address @until
    def emu_start(self, begin, until, count=0):
        insts = 0
        self.executing = True
        try:
            while self.executing and self.reg.pc != until:
                #print "%s: PC: %s" % (insts, hex(self.reg.pc))

                self.bbc.tick()
                insts += 1
                if count and insts >= count:
                    break
        finally:
            self.executing = False

    # stop emulation
    def emu_stop(self):
        self.executing = False

    # return the value of a register
    def reg_read(self, reg_id):
        dispatch = self.reg_dispatch.get(reg_id)
        if not dispatch:
            raise PbError(PbConstants.PB_ERR_ARG)

        return dispatch[0]()

    # write to a register
    def reg_write(self, reg_id, value):
        dispatch = self.reg_dispatch.get(reg_id)
        if not dispatch:
            raise PbError(PbConstants.PB_ERR_ARG)

        dispatch[1](value)

    # read data from memory
    def mem_read(self, address, size):
        return self.memory.readBytes(address, size)

    # write to memory
    def mem_write(self, address, data):
        self.memory.writeBytes(address, data)

    def hook_add(self, htype, callback, user_data=None, begin=1, end=0, arg1=0):
        hook = PbHook(self, htype, callback, user_data=user_data, begin=begin, end=end)
        if htype & PbConstants.PB_HOOK_CODE:
            self.dispatch.hook_add(hook)
        return hook

    def hook_del(self, hook):
        if hook.htype & PbConstants.PB_HOOK_CODE:
            self.dispatch.hook_del(hook)
