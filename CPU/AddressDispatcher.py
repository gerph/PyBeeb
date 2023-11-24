
class AddressDispatcher(object):
    def __init__(self, memory, registerBank):
        self.registers = registerBank
        self.memory = memory

    def implicit(self):
        return None

    def accumulator(self):
        return None

    def immediate(self):
        return self.registers.pc + 1

    def zeroPage(self):
        return self.memory.readByte( self.registers.pc + 1)

    def zeroPageX(self):
        offset = self.memory.readByte( self.registers.pc + 1)
        addr = offset + self.registers.x
        return addr & 0xff

    def zeroPageY(self):
        offset = self.memory.readByte( self.registers.pc + 1)
        addr = offset + self.registers.y
        return addr & 0xff

    def relative(self):
        offset = self.memory.readSignedByte( self.registers.pc + 1)
        return offset + self.registers.nextPC

    def absolute(self):
        return self.memory.readWord(self.registers.pc + 1)

    def absoluteX(self):
        offset = self.memory.readWord(self.registers.pc + 1)
        return self.registers.x + offset

    def absoluteY(self):
        offset = self.memory.readWord(self.registers.pc + 1)
        return self.registers.y + offset

    def indirect(self):
        addr = self.memory.readWord(self.registers.pc + 1)
        return self.memory.readWord(addr)

    def indirectX(self):
        addr = self.memory.readByte(self.registers.pc + 1) + self.registers.x
        addr = addr & 0xff
        return self.memory.readWord(addr)

    def indirectY(self):
        addr = self.memory.readByte(self.registers.pc + 1)
        return self.memory.readWord(addr) + self.registers.y

    def implicitRead(self):
        return None

    def accumulatorRead(self):
        return self.registers.a

    def immediateRead(self):
        return self.memory.readByte(self.immediate())

    def zeroPageRead(self):
        return self.memory.readByte(self.zeroPage())

    def zeroPageXRead(self):
        return self.memory.readByte(self.zeroPageX())

    def zeroPageYRead(self):
        return self.memory.readByte(self.zeroPageY())

    def relativeRead(self):
        return self.memory.readByte(self.relative()) # hack hack hack

    def absoluteRead(self):
        return self.memory.readByte(self.absolute())

    def absoluteXRead(self):
        return self.memory.readByte(self.absoluteX())

    def absoluteYRead(self):
        return self.memory.readByte(self.absoluteY())

    def indirectRead(self):
        return self.memory.readByte(self.indirect())

    def indirectXRead(self):
        return self.memory.readByte(self.indirectX())

    def indirectYRead(self):
        return self.memory.readByte(self.indirectY())
