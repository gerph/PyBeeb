from . import ROM

BASE = 0xc000
TOP = 0xffff

class MOS(object):
    def readByte(self, address):
        return ROM.rom_os12[address]

def writeByte(self, address, value):
        pass