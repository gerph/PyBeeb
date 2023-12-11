'''
Created on 12 Oct 2011

@author: chris.whitworth
'''

class RegisterBank(object):

    def __init__(self):
        self.pc = 0x0000
        self.sp = 0xff
        self.a  = 0x00
        self.x  = 0x00
        self.y  = 0x00
        self.nextPC = 0x0000

        self.carry = False
        self.zero = False
        self.int = False
        self.dec = False
        self.brk = False
        self.overflow = False
        self.negative = False

    def __repr__(self):
        state = []
        state.append('pc: &%04x' % (self.pc,))
        state.append('sp: &%02x' % (self.sp,))
        state.append('a: &%02x' % (self.a,))
        state.append('x: &%02x' % (self.x,))
        state.append('y: &%02x' % (self.y,))
        return "<{}({})>".format(self.__class__.__name__, ', '.join(state))


    def ps(self):
        return ( (1 if self.carry else 0) |
                 (2 if self.zero else 0) |
                 (4 if self.int else 0) |
                 (8 if self.dec else 0) |
                 (16 if self.brk else 0) |
                 (64 if self.overflow else 0) |
                 (128 if self.negative else 0) )

    def setPS(self, value):
        self.carry = (value & 0x1) != 0
        self.zero = (value & 0x2) != 0
        self.int = (value & 0x4) != 0
        self.dec = (value & 0x8) != 0
        self.brk = (value & 0x10) != 0
        self.overflow = (value & 0x40) != 0
        self.negative = (value & 0x80) != 0

    def reset(self):
        self.x = 0
        self.a = 0
        self.y = 0
        self.pc = 0
        self.nextPC = 0
        self.sp = 0xff
        self.setPS(0)

    def status(self):
        sys.stdout.write("%s%s.%s%s%s%s%s" % (
                                              "N" if self.negative else "-",
                                              "V" if self.overflow else "-",
                                              "B" if self.brk else "-",
                                              "D" if self.dec else "-",
                                              "I" if self.int else "-",
                                              "Z" if self.zero else "-",
                                              "C" if self.carry else "-"))
        sys.stdout.write("A: %s X: %s Y: %s" % (hex(self.a), hex(self.x), hex(self.y)))
        sys.stdout.write("PC: %s SP: %s\n" % (hex(self.pc), hex(self.sp)))
