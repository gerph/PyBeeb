'''
Created on 12 Oct 2011

@author: chris.whitworth
'''
import pybeeb.CPU.Dispatch
import pybeeb.CPU.AddressDispatcher as AddressDispatch
import pybeeb.CPU.InstructionDecoder as Decoder
import pybeeb.CPU.Memory
import pybeeb.CPU.Registers
import pybeeb.ArrayMemMapper as ArrayMemMapper
from . import CPU


class ExecutionUnit(object):
    def ADC(self, data, address):
        return "ADC %s" % hex(data)

    def AND(self, data, address):
        return "AND %s" % hex(data)

    def ASL(self, data, address):
        return "ASL %s" % hex(data)

    def BCC(self, data, address):
        return "BCC %s" % hex(address)

    def BCS(self, data, address):
        return "BCS %s" % hex(address)

    def BEQ(self, data, address):
        return "BEQ %s" % hex(address)

    def BIT(self, data, address):
        return "BIT %s" % hex(data)

    def BMI(self, data, address):
        return "BMI %s" % hex(address)

    def BNE(self, data, address):
        return "BNE %s" % hex(address)

    def BPL(self, data, address):
        return "BPL %s" % hex(data)

    def BRK(self, data, address):
        return "BRK"

    def BVC(self, data, address):
        return "BVC %s" % hex(address)

    def BVS(self, data, address):
        return "BVS %s" % hex(address)

    def CLC(self, data, address):
        return "CLC"

    def CLD(self, data, address):
        return "CLD"

    def CLI(self, data, address):
        return "CLI"

    def CLV(self, data, address):
        return "CLV"

    def CMP(self, data, address):
        return "CMP %s" % hex(data)

    def CPX(self, data, address):
        return "CPX %s" % hex(data)

    def CPY(self, data, address):
        return "CPY %s" % hex(data)

    def DEC(self, data, address):
        return "DEC %s" % hex(data)

    def DEX(self, data, address):
        return "DEX"

    def DEY(self, data, address):
        return "DEY"

    def EOR(self, data, address):
        return "EOR %s" % hex(data)

    def INC(self, data, address):
        return "INC %s" % hex(data)

    def INX(self, data, address):
        return "INX"

    def INY(self, data, address):
        return "INY"

    def JMP(self, data, address):
        return "JMP %s" % hex(address)

    def JSR(self, data, address):
        return "JSR %s" % hex(address)

    def LDA(self, data, address):
        return "LDA %s" % hex(data)

    def LDX(self, data, address):
        return "LDX %s" % hex(data)

    def LDY(self, data, address):
        return "LDY %s" % hex(data)

    def LSR(self, data, address):
        return "LSR %s" % hex(data)

    def NOP(self, data, address):
        return "NOP"

    def ORA(self, data, address):
        return "ORA %s" % hex(data)

    def PHA(self, data, address):
        return "PHA"

    def PHP(self, data, address):
        return "PHP"

    def PLA(self, data, address):
        return "PLA"

    def PLP(self, data, address):
        return "PLP"

    def ROL(self, data, address):
        return "ROL %s" % hex(data)

    def ROR(self, data, address):
        return "ROR %s" % hex(data)

    def RTI(self, data, address):
        return "RTI"

    def RTS(self, data, address):
        return "RTS"

    def SBC(self, data, address):
        return "SBC %s" % hex(data)

    def SEC(self, data, address):
        return "SEC"

    def SED(self, data, address):
        return "SED"

    def SEI(self, data, address):
        return "SEI"

    def STA(self, data, address):
        return "STA %s" % hex(data)

    def STX(self, data, address):
        return "STX %s" % hex(data)

    def STY(self, data, address):
        return "STY %s" % hex(data)

    def TAX(self, data, address):
        return "TAX"

    def TAY(self, data, address):
        return "TAY"

    def TSX(self, data, address):
        return "TSX"

    def TXA(self, data, address):
        return "TXA"

    def TXS(self, data, address):
        return "TXS"

    def TYA(self, data, address):
        return "TYA"

    def UNDEFINED(self, data, address):
        return "UNDEFINED"


class WritebackDispatcher(object):
    def A(self, value, location):
        pass

    def X(self, value, location):
        pass

    def Y(self, value, location):
        pass

    def memory(self, value, location):
        pass

    def PC(self, value, location):
        pass

    def SP(self, value, location):
        pass

    def PS(self, value, location):
        pass

    def NW(self, value, location):
        pass


class Disassembler(object):
    def __init__(self, decoderTablePath):
        executionDispatcher = ExecutionUnit()
        self.memory = CPU.Memory.Memory()
        self.registers = CPU.Registers.RegisterBank()
        addressDispatcher = AddressDispatch.AddressDispatcher(self.memory, self.registers)
        writebackDispatcher = WritebackDispatcher()
        decoder = Decoder.Decoder(decoderTablePath)
        self.dispatch = CPU.Dispatch.Dispatcher(decoder, addressDispatcher, executionDispatcher, writebackDispatcher, self.memory, self.registers)

    class Generator(object):
        def __init__(self, dispatcher):
            self.dispatcher = dispatcher

        def __iter__(self):
            return self.next()

        def next(self):
            while True:
                yield self.dispatcher.dispatch()

    def disassemble(self, data):
        self.memory.map( (0, len(data)), ArrayMemMapper.Mapper(data))
        generator = self.Generator(self.dispatch)
        for decode in generator:
            print( "%s " % (self.registers.pc)),
            print(": %s " % (decode))
