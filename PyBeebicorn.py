"""
Unicorn-like interface for PyBeeb.

Allows code that was written for Unicorn to work with PyBeeb with minimal
modifications (or just reamapping the variable names).
"""

import os.path

import CPU.Memory as Memory
import CPU.Registers as Registers
import CPU.AddressDispatcher as AddressDispatcher
import CPU.Writeback as Writeback
import CPU.ExecutionUnit as ExecutionUnit
import CPU.Dispatch as Dispatch
import CPU.InstructionDecoder as Decoder
import Debugging.Combiner
import Debugging.Writeback
import Debugging.ExecutionUnit
import BBCMicro.System


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

    def __init__(self, pb, callback, user_data=None, begin=1, end=0):
        self.pb = pb
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


class Pb(object):
    insts_filename = os.path.join(os.path.dirname(__file__), 'insts.csv')

    def __init__(self):
        # We only support 6502, so there is no architecture or mode flag.
        self.mem = Memory.Memory()
        self.reg = Registers.RegisterBank()
        addrDispatch = AddressDispatcher.AddressDispatcher(self.mem, self.reg)

        execDispatch = ExecutionUnit.ExecutionDispatcher(self.mem,self.reg)
        execLogger = Debugging.ExecutionUnit.LoggingExecutionUnit()
        combinedExec = Debugging.Combiner.Dispatcher( (execLogger, execDispatch) )

        writebackDispatch = Writeback.Dispatcher(self.mem,self.reg)
        writebackLogger = Debugging.Writeback.LoggingDispatcher()
        combinedWriteback = Debugging.Combiner.Dispatcher( (writebackLogger, writebackDispatch) )

        decoder = Decoder.Decoder(self.insts_filename)

        dispatch = Dispatch.Dispatcher(decoder, addrDispatch,
                                       execDispatch, writebackDispatch,
                                       self.mem, self.reg)

        self.bbc = BBCMicro.System.Beeb(dispatch)

        self.executing = False

        def write_pc(v):
            self.reg.pc = v

        def write_sp(v):
            self.reg.sp = v

        def write_a(v):
            self.reg.a = v

        def write_x(v):
            self.reg.x = v

        def write_y(v):
            self.reg.y = v

        self.reg_dispatch = {
                PbConstants.PB_6502_REG_PC: (lambda: self.reg.pc, write_pc),
                PbConstants.PB_6502_REG_SP: (lambda: self.reg.sp, write_sp),
                PbConstants.PB_6502_REG_A: (lambda: self.reg.a, write_a),
                PbConstants.PB_6502_REG_X: (lambda: self.reg.x, write_x),
                PbConstants.PB_6502_REG_Y: (lambda: self.reg.y, write_y),
                PbConstants.PB_6502_REG_PS: (lambda: self.reg.ps(), lambda v: self.reg.setPS(v)),
            }

        # Execution hooks - when we hit an address in the range we call the hook
        self.hook_exec = []

    # emulate from @begin, and stop when reaching address @until
    def emu_start(self, begin, until, count=0):
        insts = 0
        self.executing = True
        try:
            while self.executing and self.reg.pc != until:
                #print "%s: PC: %s" % (insts, hex(self.reg.pc))

                for hook in self.hook_exec:
                    if self.reg.pc in hook:
                        hook.call(self.reg.pc, 1)

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
            raise PbError(ERR_ARG)

        return dispatch[0]()

    # write to a register
    def reg_write(self, reg_id, value):
        dispatch = self.reg_dispatch.get(reg_id)
        if not dispatch:
            raise PbError(ERR_ARG)

        dispatch[1](value & 0xFF)

    # read data from memory
    def mem_read(self, address, size):
        return self.memory.readBytes(address, size)

    # write to memory
    def mem_write(self, address, data):
        self.memory.writeBytes(address, data)

    def hook_add(self, htype, callback, user_data=None, begin=1, end=0, arg1=0):
        hook = PbHook(self, callback, user_data=user_data, begin=begin, end=end)
        if htype & PbConstants.PB_HOOK_CODE:
            self.hook_exec.append(hook)
        return hook

    def hook_del(self, hook):
        if hook in self.hook_exec:
            self.hook_exec.remove(hook)
