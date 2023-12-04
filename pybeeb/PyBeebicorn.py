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


class Dissassemble6502(object):

    def __init__(self, decoder):
        self.decoder = decoder
        self.disassembly_table = {
                "imp": self.operands_imp,
                "acc": self.operands_acc,
                "imm": self.operands_imm,
                "zp" : self.operands_zp,
                "zpx": self.operands_zpx,
                "zpy": self.operands_zpy,
                "rel": self.operands_rel,
                "abs": self.operands_abs,
                "abx": self.operands_abx,
                "aby": self.operands_aby,
                "ind": self.operands_ind,
                "inx": self.operands_inx,
                "iny": self.operands_iny,
           }

    def operands_imp(self, pc):
        return ("", '')

    def operands_acc(self, pc):
        return ("", '')

    def operands_imm(self, pc):
        b = self.read_byte(pc + 1)
        return ("#%s" % (b,), "= &%02X" % (b,) if b > 10 else '')

    def operands_zp(self, pc):
        b = self.read_byte(pc + 1)
        return ("&%02X" % (b,), '')

    def operands_zpx(self, pc):
        b = self.read_byte(pc + 1)
        return ("&%02X, X" % (b,), "-> &%02X" % (b + self.reg_x(),))

    def operands_zpy(self, pc):
        b = self.read_byte(pc + 1)
        return ("&%02X, Y" % (b,), "-> &%02X" % (b + self.reg_y(),))

    def operands_rel(self, pc):
        return ("&%04X" % (pc + self.read_signedbyte(pc + 1) + 2,), '')

    def operands_abs(self, pc):
        return ("&%04X" % (self.read_word(pc + 1),), '')

    def operands_abx(self, pc):
        addr = self.read_word(pc + 1)
        return ("&%04X, X" % (addr,), "-> &%02X" % (addr + self.reg_x(),))

    def operands_aby(self, pc):
        addr = self.read_word(pc + 1)
        return ("&%04X, Y" % (addr,), "-> &%02X" % (addr + self.reg_y(),))

    def operands_ind(self, pc):
        addr = self.read_word(pc + 1)
        return ("(&%04X)" % (addr,), "-> &%04X" % (self.read_word(addr)),)

    def operands_inx(self, pc):
        addr = self.read_byte(pc + 1)
        result = addr + self.reg_x()
        result = result & 0xFF
        result = self.read_word(addr)
        return ("(&%02X, X)" % (addr,), "-> &%04X" % (result,))

    def operands_iny(self, pc):
        addr = self.read_byte(pc + 1)
        result = self.read_word(addr) + self.reg_y()
        return ("(&%02X), Y" % (addr,), "-> &%04X" % (result,))

    def read_byte(self, address):
        raise NotImplementedError("read_byte not implemented for {}".format(self.__class__.__name__))

    def read_signedbyte(self, address):
        raise NotImplementedError("read_signedbyte not implemented for {}".format(self.__class__.__name__))

    def read_word(self, address):
        raise NotImplementedError("read_word not implemented for {}".format(self.__class__.__name__))

    def reg_x(self):
        raise NotImplementedError("reg_x not implemented for {}".format(self.__class__.__name__))

    def reg_y(self):
        raise NotImplementedError("reg_y not implemented for {}".format(self.__class__.__name__))

    def disassemble(self, pc):
        opcode = self.read_byte(pc)
        inst = self.decoder.instruction(opcode)
        mode = self.decoder.addressingMode(opcode)
        (params, comment) = self.disassembly_table[mode](pc)
        if comment:
            formatted = "%-8s  ; %s" % (params, comment)
        else:
            formatted = params
        return (inst, formatted, params, comment)


class Disassemble6502Pb(Dissassemble6502):
    def __init__(self, pb):
        super(Disassemble6502Pb, self).__init__(pb.dispatch.decoder)
        self.pb = pb

    def read_byte(self, address):
        return self.pb.memory.readByte(address)

    def read_signedbyte(self, address):
        b = self.pb.memory.readByte(address)
        if b & 0x80:
            b = b - 256
        return b

    def read_word(self, address):
        return self.pb.memory.readWord(address)

    def reg_x(self):
        return self.pb.reg.x

    def reg_y(self):
        return self.pb.reg.y


class PbHook(object):

    def __init__(self, pb, htype, callback, user_data=None, begin=1, end=0):
        self.pb = pb
        self.htype = htype
        self.callback = callback
        self.user_data = user_data
        self.address = begin
        self.end = end
        self.size = end - begin

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


class PbMemory(Memory.Memory):

    def __init__(self, pb):
        super(PbMemory, self).__init__()
        self.pb = pb
        # We keep a list of the registered hooks, which are ordered.
        # We also keep a list of the hooks keyed by address in the 'hook_simple_*'
        # dictionary. These will be used if all the hooks that are registered are
        # a single byte long, and none of them use the same address.
        # This is likely to be the most common case, and using a dictionary
        # we can avoid a more lengthy lookup by searching a list.
        self.hook_read = []
        self.hook_simple_read = {}
        self.hook_write = []
        self.hook_simple_write = {}

    def hook_add(self, hook):
        if hook.htype & PbConstants.PB_HOOK_MEM_READ:
            if not self.hook_read or self.hook_simple_read:
                # This is the first hook, or there are simple hooks present, so we
                # can apply simple hooks.
                if hook.size == 1 and not self.hook_simple_read.get(hook.address):
                    # This is a simple hook, and there's no other hook in the address
                    self.hook_simple_read[hook.address] = hook
                else:
                    # This is not a simple hook (or another hook at the address exists)
                    # and there exist simple hooks, so clear them. We'll revert to slow
                    # hooks.
                    self.hook_simple_read = {}
            self.hook_read.append(hook)

        if hook.htype & PbConstants.PB_HOOK_MEM_WRITE:
            if not self.hook_write or self.hook_simple_write:
                # This is the first hook, or there are simple hooks present, so we
                # can apply simple hooks.
                if hook.size == 1 and not self.hook_simple_write.get(hook.address):
                    # This is a simple hook, and there's no other hook in the address
                    self.hook_simple_write[hook.address] = hook
                else:
                    # This is not a simple hook (or another hook at the address exists)
                    # and there exist simple hooks, so clear them. We'll revert to slow
                    # hooks.
                    self.hook_simple_write = {}
            self.hook_write.append(hook)

    def hook_del(self, hook):
        if hook in self.hook_read:
            self.hook_read.remove(hook)
            if hook.address in self.hook_simple_read:
                del self.hook_simple_read[hook.address]
        if hook in self.hook_write:
            self.hook_write.remove(hook)
            if hook.address in self.hook_simple_write:
                del self.hook_simple_write[hook.address]

    def readByte(self, address, skip_hook=False):
        # Dispatch any hooks for this byte
        if not skip_hook and self.hook_read:
            if self.hook_simple_read:
                hook = self.hook_simple_read.get(address, None)
                if hook:
                    hook.call(PbConstants.PB_MEM_READ, address, 1, 0)
            else:
                # There's no simple hooks present, but there are hooks,
                # so we need to process them
                for hook in self.hook_read:
                    if address in hook:
                        hook.call(PbConstants.PB_MEM_READ, address, 1, 0)

        return super(PbMemory, self).readByte(address)

    def writeByte(self, address, value, skip_hook=False):
        # Dispatch any hooks for this byte
        if not skip_hook and self.hook_write:
            if self.hook_simple_write:
                hook = self.hook_simple_write.get(address, None)
                if hook:
                    hook.call(PbConstants.PB_MEM_WRITE, address, 1, value)
            else:
                # There's no simple hooks present, but there are hooks,
                # so we need to process them
                for hook in self.hook_write:
                    if address in hook:
                        hook.call(PbConstants.PB_MEM_WRITE, address, 1, value)

        super(PbMemory, self).writeByte(address, value)

    def readBytes(self, address, size, skip_hook=False):
        """
        Read multiple bytes into a bytearray / mapped region.
        """

        # Dispatch any hooks for this range
        if not skip_hook:
            for hook in self.hook_read:
                if (address, size) in hook:
                    # Report only the region of the read that is in the hook
                    bound_address = max(address, min(hook.address, address + size))
                    bound_end = min(address + size, max(hook.end, address + size))
                    hook.call(PbConstants.PB_MEM_READ, bound_address, bound_end - bound_address, 0)

        return super(PbMemory, self).readBytes(address, size)

    def writeBytes(self, address, value, skip_hook=False):
        """
        Read multiple bytes into a bytearray / mapped region.
        """
        # Dispatch any hooks for this range
        if not skip_hook:
            size = len(value)
            for hook in self.hook_write:
                if (address, size) in hook:
                    # Report only the region of the write that is in the hook
                    bound_address = max(address, min(hook.address, address + size))
                    bound_end = min(address + size, max(hook.end, address + size))
                    bound_value = value[bound_address - address:bound_end - address]
                    hook.call(PbConstants.PB_MEM_READ, bound_address, bound_end - bound_address, bound_value)

        super(PbMemory, self).writeBytes(address, value)


class Pb(object):
    """
    PyBeepicorn main object - similar to the Uc() objects in Unicorn.
    """
    insts_filename = os.path.join(os.path.dirname(__file__), 'insts.csv')

    def __init__(self):
        # We only support 6502, so there is no architecture or mode flag.
        self.memory = PbMemory(self)
        self.reg = Registers.RegisterBank()
        addrDispatch = AddressDispatcher.AddressDispatcher(self.memory, self.reg)

        execDispatch = ExecutionUnit.ExecutionDispatcher(self.memory,self.reg)
        writebackDispatch = Writeback.Dispatcher(self.memory,self.reg)

        decoder = Decoder.Decoder(self.insts_filename)

        self.dispatch = PbDispatcher(self, decoder, addrDispatch,
                                     execDispatch, writebackDispatch,
                                     self.memory, self.reg)

        self.bbc = BBCMicro.System.Beeb(self.dispatch)
        self.dis = Disassemble6502Pb(self)

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
        if htype & (PbConstants.PB_HOOK_MEM_READ | PbConstants.PB_HOOK_MEM_WRITE):
            self.memory.hook_add(hook)
        return hook

    def hook_del(self, hook):
        if hook.htype & PbConstants.PB_HOOK_CODE:
            self.dispatch.hook_del(hook)
        if hook.htype & (PbConstants.PB_HOOK_MEM_READ | PbConstants.PB_HOOK_MEM_WRITE):
            self.memory.hook_del(hook)
