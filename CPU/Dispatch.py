'''
Created on 12 Oct 2011

@author: chris.whitworth
'''

class Dispatcher:
    def __init__(self, decoder, addressDispatcher, executionDispatcher, writebackDispatcher, memory, registers):
        self.decoder = decoder
        self.memory = memory
        self.registers = registers
        self.addressTable = { "imp": addressDispatcher.implicit,
                                 "acc": addressDispatcher.accumulator,
                                 "imm": addressDispatcher.immediate,
                                 "zp" : addressDispatcher.zeroPage,
                                 "zpx": addressDispatcher.zeroPageX,
                                 "zpy": addressDispatcher.zeroPageY,
                                 "rel": addressDispatcher.relative,
                                 "abs": addressDispatcher.absolute,
                                 "abx": addressDispatcher.absoluteX,
                                 "aby": addressDispatcher.absoluteY,
                                 "ind": addressDispatcher.indirect,
                                 "inx": addressDispatcher.indirectX,
                                 "iny": addressDispatcher.indirectY
                               }
        self.dataTable = { "imp": addressDispatcher.implicitRead,
                                 "acc": addressDispatcher.accumulatorRead,
                                 "imm": addressDispatcher.immediateRead,
                                 "zp" : addressDispatcher.zeroPageRead,
                                 "zpx": addressDispatcher.zeroPageXRead,
                                 "zpy": addressDispatcher.zeroPageYRead,
                                 "rel": addressDispatcher.relativeRead,
                                 "abs": addressDispatcher.absoluteRead,
                                 "abx": addressDispatcher.absoluteXRead,
                                 "aby": addressDispatcher.absoluteYRead,
                                 "ind": addressDispatcher.indirectRead,
                                 "inx": addressDispatcher.indirectXRead,
                                 "iny": addressDispatcher.indirectYRead
                               }

        self.executionTable = { "ADC" : executionDispatcher.ADC,
                                "AND" : executionDispatcher.AND,
                                "ASL" : executionDispatcher.ASL,
                                "BCC" : executionDispatcher.BCC,
                                "BCS" : executionDispatcher.BCS,
                                "BEQ" : executionDispatcher.BEQ,
                                "BIT" : executionDispatcher.BIT,
                                "BMI" : executionDispatcher.BMI,
                                "BNE" : executionDispatcher.BNE,
                                "BPL" : executionDispatcher.BPL,
                                "BRK" : executionDispatcher.BRK,
                                "BVC" : executionDispatcher.BVC,
                                "BVS" : executionDispatcher.BVS,
                                "CLC" : executionDispatcher.CLC,
                                "CLD" : executionDispatcher.CLD,
                                "CLI" : executionDispatcher.CLI,
                                "CLV" : executionDispatcher.CLV,
                                "CMP" : executionDispatcher.CMP,
                                "CPX" : executionDispatcher.CPX,
                                "CPY" : executionDispatcher.CPY,
                                "DEC" : executionDispatcher.DEC,
                                "DEX" : executionDispatcher.DEX,
                                "DEY" : executionDispatcher.DEY,
                                "EOR" : executionDispatcher.EOR,
                                "INC" : executionDispatcher.INC,
                                "INX" : executionDispatcher.INX,
                                "INY" : executionDispatcher.INY,
                                "JMP" : executionDispatcher.JMP,
                                "JSR" : executionDispatcher.JSR,
                                "LDA" : executionDispatcher.LDA,
                                "LDX" : executionDispatcher.LDX,
                                "LDY" : executionDispatcher.LDY,
                                "LSR" : executionDispatcher.LSR,
                                "NOP" : executionDispatcher.NOP,
                                "ORA" : executionDispatcher.ORA,
                                "PHA" : executionDispatcher.PHA,
                                "PHP" : executionDispatcher.PHP,
                                "PLA" : executionDispatcher.PLA,
                                "PLP" : executionDispatcher.PLP,
                                "ROL" : executionDispatcher.ROL,
                                "ROR" : executionDispatcher.ROR,
                                "RTI" : executionDispatcher.RTI,
                                "RTS" : executionDispatcher.RTS,
                                "SBC" : executionDispatcher.SBC,
                                "SEC" : executionDispatcher.SEC,
                                "SED" : executionDispatcher.SED,
                                "SEI" : executionDispatcher.SEI,
                                "STA" : executionDispatcher.STA,
                                "STX" : executionDispatcher.STX,
                                "STY" : executionDispatcher.STY,
                                "TAX" : executionDispatcher.TAX,
                                "TAY" : executionDispatcher.TAY,
                                "TSX" : executionDispatcher.TSX,
                                "TXA" : executionDispatcher.TXA,
                                "TXS" : executionDispatcher.TXS,
                                "TYA" : executionDispatcher.TYA,
                                "UNDEFINED" : executionDispatcher.UNDEFINED
                                }
        self.writebackTable = { "A" : writebackDispatcher.A,
                                "X" : writebackDispatcher.X,
                                "Y" : writebackDispatcher.Y,
                                "M" : writebackDispatcher.memory,
                                "PC" : writebackDispatcher.PC,
                                "SP" : writebackDispatcher.SP,
                                "PS" : writebackDispatcher.PS,
                                "NW" : writebackDispatcher.NW
                                }

    def dataDecode(self, opcode):
        addressingMode = self.decoder.addressingMode(opcode)
        return self.dataTable[addressingMode]()

    def addressDecode(self, opcode):
        addressingMode = self.decoder.addressingMode(opcode)
        return self.addressTable[addressingMode]()

    def dispatch(self):
        #Decode
        opcode = self.memory.readByte(self.registers.pc)
        instruction = self.decoder.instruction(opcode)
        writeback = self.decoder.writeback(opcode)
        self.registers.nextPC = self.registers.pc + self.decoder.instructionLength(opcode)

        #execute
        data = self.dataDecode(opcode)
        address = self.addressDecode(opcode)
        result = self.executionTable[instruction](data, address)

        if result != None:
            self.writebackTable[writeback](result, address)

        self.registers.pc = self.registers.nextPC

        return result

    def reset(self):
        self.registers.reset()
        self.registers.pc = self.memory.readWord(0xfffc)