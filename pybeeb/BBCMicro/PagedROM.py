import ROM

BASE = 0x8000
TOP = 0xbfff

class PagedROM(object):
    def __init__(self):
        self.rom = None
        self.index = 0

    def setPagedROM(self, index):
        self.index = index
        if index == 15:
            self.rom = ROM.rom_basic2
        else:
            self.rom = None

    def readByte(self, addr):
        if self.rom != None:
            return self.rom[addr]
        else:
            return 0

    def writeByte(self, addr, value):
        pass