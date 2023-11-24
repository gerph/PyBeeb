BASE = 0xfe00
TOP = 0xfeff

class Sheila(object):

    def __init__(self, bbc):
        self.bbc = bbc

    def readByte(self, addr):
        return 0

    def writeByte(self, addr, value):
        if addr == (0xfe30 - BASE):
            self.bbc.setPagedROM(value & 0x0f)
        else:
            pass
