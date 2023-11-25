'''
Created on 12 Oct 2011

@author: chris.whitworth
'''
import CPU.Dispatch as Dispatch
import CPU.AddressDispatcher as AddressDispatch
import CPU.InstructionDecoder as Decoder
import CPU.Memory as Memory
import CPU.Registers as Registers
import ArrayMemMapper

import logging

class ExecutionUnit(object):
    def ADC(self, data):
        return "ADC %s" % hex(data)

    def AND(self, data):
        return "AND %s" % hex(data)

    def ASL(self, data):
        return "ASL %s" % hex(data)

    def BCC(self, data):
        return "BCC %s" % hex(data)

    def BCS(self, data):
        return "BCS %s" % hex(data)

    def BEQ(self, data):
        return "BEQ %s" % hex(data)

    def BIT(self, data):
        return "BIT %s" % hex(data)

    def BMI(self, data):
        return "BMI %s" % hex(data)

    def BNE(self, data):
        return "BNE %s" % hex(data)

    def BPL(self, data):
        return "BPL %s" % hex(data)

    def BRK(self, data):
        return "BRK"

    def BVC(self, data):
        return "BVC %s" % hex(data)

    def BVS(self, data):
        return "BVS %s" % hex(data)

    def CLC(self, data):
        return "CLC"

    def CLD(self, data):
        return "CLD"

    def CLI(self, data):
        return "CLI"

    def CLV(self, data):
        return "CLV"

    def CMP(self, data):
        return "CMP %s" % hex(data)

    def CPX(self, data):
        return "CPX %s" % hex(data)

    def CPY(self, data):
        return "CPY %s" % hex(data)

    def DEC(self, data):
        return "DEC %s" % hex(data)

    def DEX(self, data):
        return "DEX"

    def DEY(self, data):
        return "DEY"

    def EOR(self, data):
        return "EOR %s" % hex(data)

    def INC(self, data):
        return "INC %s" % hex(data)

    def INX(self, data):
        return "INX"

    def INY(self, data):
        return "INY"

    def JMP(self, data):
        return "JMP %s" % hex(data)

    def JSR(self, data):
        return "JSR %s" % hex(data)

    def LDA(self, data):
        return "LDA %s" % hex(data)

    def LDX(self, data):
        return "LDX %s" % hex(data)

    def LDY(self, data):
        return "LDY %s" % hex(data)

    def LSR(self, data):
        return "LSR %s" % hex(data)

    def NOP(self, data):
        return "NOP"

    def ORA(self, data):
        return "ORA %s" % hex(data)

    def PHA(self, data):
        return "PHA"

    def PHP(self, data):
        return "PHP"

    def PLA(self, data):
        return "PLA"

    def PLP(self, data):
        return "PLP"

    def ROL(self, data):
        return "ROL %s" % hex(data)

    def ROR(self, data):
        return "ROR %s" % hex(data)

    def RTI(self, data):
        return "RTI"

    def RTS(self, data):
        return "RTS"

    def SBC(self, data):
        return "SBC %s" % hex(data)

    def SEC(self, data):
        return "SEC"

    def SED(self, data):
        return "SED"

    def SEI(self, data):
        return "SEI"

    def STA(self, data):
        return "STA %s" % hex(data)

    def STX(self, data):
        return "STX %s" % hex(data)

    def STY(self, data):
        return "STY %s" % hex(data)

    def TAX(self, data):
        return "TAX"

    def TAY(self, data):
        return "TAY"

    def TSX(self, data):
        return "TSX"

    def TXA(self, data):
        return "TXA"

    def TXS(self, data):
        return "TXS"

    def TYA(self, data):
        return "TYA"

    def UNDEFINED(self, data):
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
        self.memory = Memory.Memory()
        self.registers = Registers.RegisterBank()
        addressDispatcher = AddressDispatch.AddressDispatcher(self.memory, self.registers)
        writebackDispatcher = WritebackDispatcher()
        decoder = Decoder.Decoder(decoderTablePath)
        self.dispatch = Dispatch.Dispatcher(decoder, addressDispatcher, executionDispatcher, writebackDispatcher, self.memory, self.registers)

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
            print "%s " % (self.registers.pc),
            print ": %s " % (decode)
