"""
Python interfaces to allow calling the MOS interfaces.
"""

from .Emulation import PbConstants, StackOverflowException, StackUnderflowException


# Python 2/3 support
try:
    unicode
except:
    unicode = str


class ExecutionComplete(Exception):
    pass


class MOS(object):
    return_address = 0xFFFF

    def __init__(self, pb):
        self.pb = pb

    def push_byte(self, value):
        self.pb.memory.writeByte(self.pb.regs.sp + 0x100, value)
        self.pb.regs.sp -= 1
        if self.pb.regs.sp < 0x00:
            raise StackOverflowException()

    def pull_byte(self):
        self.pb.regs.sp += 1
        if self.pb.regs.sp > 0xff:
            raise StackUnderflowException()

        return self.pb.memory.readByte(self.pb.regs.sp + 0x100)

    def push_word(self, value):
        self.push_byte(value >> 8)
        self.push_byte(value & 0xff)

    def pull_word(self):
        lw = self.pull_byte()
        hw = self.pull_byte() << 8
        return lw + hw

    def push_pc(self):
        self.push_word(self.pb.regs.pc)

    def pop_pc(self):
        self.pb.regs.pc = self.pull_word()
    rts = pop_pc

    def _execution_complete(self):
        raise ExecutionComplete("Return from internal call (abnormal)")

    def call(self, address, a=None, x=None, y=None, preserve_state=True):
        """
        Call a routine in the system (doesn't have to be a MOS routine).

        @param address:     Address to call
        @param a, x, y:     Register values to use, or None to not set them
        @param preserve_state:  True to preserve all the calling registers
        """
        old_regs = self.pb.regs.copy()
        self.push_pc()
        self.push_word(self.return_address - 1)
        was_executing = self.pb.executing

        if a is not None:
            self.pb.regs.a = a
        if x is not None:
            self.pb.regs.x = x
        if y is not None:
            self.pb.regs.y = y

        # Add a hook so that we can exit cleanly
        self.pb.hook_add(PbConstants.PB_HOOK_CODE,
                         self._execution_complete,
                         begin=self.return_address, end=self.return_address + 1)

        try:
            self.pb.emu_start(address, until=self.return_address)
        except ExecutionComplete:
            # The emulation ended with a return from the internal call that wasn't detected
            # by emu_start. This means that we probably called to a routine that subsequently
            # called emu_start and then exited via our hook. This probably means an unbalanced
            # stack. For now we just let this be an exception.
            raise

        self.pop_pc()
        regs = self.pb.regs
        if preserve_state:
            regs = self.pb.regs.copy()
            self.pb.regs.restore(old_regs)

        self.pb.executing = was_executing
        return regs

    def oswrch(self, c):
        self.call(0xFFEE, a=c, preserve_state=True)

    def osasci(self, c):
        self.call(0xFFE3, a=c, preserve_state=True)

    def write(self, msg):
        if isinstance(msg, bytes):
            data = bytearray(msg)
        elif isinstance(msg, (str, unicode)):
            # Let's use latin-1 as our encoding for now.
            data = msg.encode('latin-1')
            data = bytearray(data)
        elif isinstance(msg, bytearray):
            data = msg
        for c in data:
            self.osasci(c)

    def writeraw(self, msg):
        if isinstance(msg, bytes):
            data = bytearray(msg)
        elif isinstance(msg, (str, unicode)):
            # Let's use latin-1 as our encoding for now.
            data = msg.encode('latin-1')
            data = bytearray(data)
        elif isinstance(msg, bytearray):
            data = msg

        for c in data:
            self.oswrch(c)
