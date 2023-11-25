'''
Created on 13 Oct 2011

@author: chris.whitworth
'''

class StackOverflowException(BaseException):
    pass
class StackUnderflowException(BaseException):
    pass

class ExecutionDispatcher(object):
    class NotImplementedException(BaseException):
        def __init__(self):
            self.instr = ""

        def __repr__(self):
            "%s is not implemented"

    def __init__(self, memory, registers):
        self.memory = memory
        self.registers = registers

    def pushByte(self, value):
        self.memory.writeByte(self.registers.sp + 0x100, value)
        self.registers.sp -= 1
        if self.registers.sp < 0x00:
            raise StackOverflowException()

    def pullByte(self):
        self.registers.sp += 1
        if self.registers.sp > 0xff:
            raise StackUnderflowException()

        return self.memory.readByte(self.registers.sp + 0x100)

    def pushWord(self, value):
        self.pushByte( value >> 8)
        self.pushByte( value & 0xff )

    def pullWord(self):
        lw = self.pullByte()
        hw = self.pullByte() << 8
        return lw + hw

    def doCompare(self, mem, reg):
        result = reg - mem
        self.registers.negative = (result < 0 or result > 127)
        self.registers.zero = (result == 0)
        self.registers.carry = (result >= 0)

    def ADC(self, data, address):
        result = self.registers.a + data + (1 if self.registers.carry else 0)
        self.registers.negative = (result & 0x80) != 0
        self.registers.carry = (result > 255)
        self.registers.zero = (result == 0)
        return result & 0xff

    def AND(self, data, address):
        result = self.registers.a & data
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def ASL(self, data, address):
        result = data << 1
        self.registers.carry = (result > 255)
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result & 0xff

    def BCC(self, data, address):
        if not self.registers.carry:
            return address
        else:
            return None

    def BCS(self, data, address):
        if self.registers.carry:
            return address
        else:
            return None

    def BEQ(self, data, address):
        if self.registers.zero:
            return address
        else:
            return None

    def BIT(self, data, address):
        result = self.registers.a & data
        self.registers.negative = (data & 0x80) != 0
        self.registers.overflow = (data & 0x40) != 0
        self.registers.zero = (result == 0)
        return None

    def BMI(self, data, address):
        if self.registers.negative:
            return address
        else:
            return None

    def BNE(self, data, address):
        if not self.registers.zero:
            return address
        else:
            return None

    def BPL(self, data, address):
        if not self.registers.negative:
            return address
        else:
            return None

    def BRK(self, data, address):
        self.registers.brk = True
        self.pushWord(self.registers.pc + 2)
        self.pushByte(self.registers.ps())
        return self.memory.readWord(0xfffe)

    def BVC(self, data, address):
        if not self.registers.overflow:
            return address
        else:
            return None

    def BVS(self, data, address):
        if self.registers.overflow:
            return address
        else:
            return None

    def CLC(self, data, address):
        self.registers.carry = False
        return None

    def CLD(self, data, address):
        self.registers.dec = False
        return None

    def CLI(self, data, address):
        self.registers.int = False
        return None

    def CLV(self, data, address):
        self.registers.overflow = False
        return None

    def CMP(self, data, address):
        self.doCompare(data, self.registers.a)
        return None

    def CPX(self, data, address):
        self.doCompare(data, self.registers.x)
        return None

    def CPY(self, data, address):
        self.doCompare(data, self.registers.y)
        return None

    def DEC(self, data, address):
        result = data - 1
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result & 0xff

    def DEX(self, data, address):
        result = self.registers.x - 1
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result & 0xff

    def DEY(self, data, address):
        result = self.registers.y - 1
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result & 0xff

    def EOR(self, data, address):
        result = self.registers.a ^ data
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def INC(self, data, address):
        result = (data + 1) & 0xff
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def INX(self, data, address):
        result = (self.registers.x + 1) & 0xff
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def INY(self, data, address):
        result = (self.registers.y + 1) & 0xff
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def JMP(self, data, address):
        return address

    def JSR(self, data, address):
        self.pushWord(self.registers.pc + 2)
        return address

    def LDA(self, data, address):
        self.registers.zero = (data == 0)
        self.registers.negative = (data & 0x80) != 0
        return data

    def LDX(self, data, address):
        self.registers.zero = (data == 0)
        self.registers.negative = (data & 0x80) != 0
        return data

    def LDY(self, data, address):
        self.registers.zero = (data == 0)
        self.registers.negative = (data & 0x80) != 0
        return data

    def LSR(self, data, address):
        self.registers.carry = (data & 0x01) != 0
        result = data >> 1
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result & 0xff

    def NOP(self, data, address):
        pass

    def ORA(self, data, address):
        result = data | self.registers.a
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def PHA(self, data, address):
        self.pushByte(self.registers.a)
        return None

    def PHP(self, data, address):
        self.pushByte(self.registers.ps())
        return None

    def PLA(self, data, address):
        result = self.pullByte()
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def PLP(self, data, address):
        result = self.pullByte()
        self.registers.setPS(result)
        return None

    def ROL(self, data, address):
        oldCarry = 0x01 if self.registers.carry else 0x00
        self.registers.carry = (data & 0x80) != 0
        result = (data << 1) & 0xff
        result = result | oldCarry
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def ROR(self, data, address):
        oldCarry = 0x80 if self.registers.carry else 0x00
        self.registers.carry = (data & 0x01) != 0
        result = (data >> 1) | (oldCarry)
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def RTI(self, data, address):
        self.registers.setPS(self.pullByte())
        self.registers.brk = False
        return self.pullWord()


    def RTS(self, data, address):
        location = self.pullWord()
        return location + 1

    def SBC(self, data, address):
        result = (~data) & 0xff
        result += self.registers.a + (1 if self.registers.carry else 0)
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        self.registers.carry = (result > 255)
        return result & 0xff

    def SEC(self, data, address):
        self.registers.carry = True
        return None

    def SED(self, data, address):
        self.registers.dec = True
        return None

    def SEI(self, data, address):
        self.registers.int = True
        return None

    def STA(self, data, address):
        return self.registers.a

    def STX(self, data, address):
        return self.registers.x

    def STY(self, data, address):
        return self.registers.y

    def TAX(self, data, address):
        result = self.registers.a
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def TAY(self, data, address):
        result = self.registers.a
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def TSX(self, data, address):
        result = self.registers.sp
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def TXA(self, data, address):
        result = self.registers.x
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def TXS(self, data, address):
        result = self.registers.x
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def TYA(self, data, address):
        result = self.registers.y
        self.registers.zero = (result == 0)
        self.registers.negative = (result & 0x80) != 0
        return result

    def UNDEFINED(self, data, address):
        pass
#        raise self.NotImplementedException()
