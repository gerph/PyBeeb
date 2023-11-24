class Decoder(object):
    def __init__(self, decodeFilename):
        decodeFile = open(decodeFilename)
        self.loadDecodeTable(decodeFile)

    def loadDecodeTable(self, decodeFile):
        self.decodeTable = {}
        for entry in decodeFile:
            (opcode, instr, addr, wb, byteLen, time) = entry.split(",")
            try:
                if instr != "":
                    self.decodeTable[int(opcode,16)] = (instr, addr, wb, int(byteLen), int(time))
                else:
                    self.decodeTable[int(opcode,16)] = ("UNDEFINED", "imp", "NW", 1, 1)
            except ValueError:
                pass

    def instruction(self, opcode):
        return self.decodeTable[opcode][0]

    def addressingMode(self, opcode):
        return self.decodeTable[opcode][1]

    def writeback(self, opcode):
        return self.decodeTable[opcode][2]

    def instructionLength(self, opcode):
        return self.decodeTable[opcode][3]

    def clockCycles(self, opcode):
        ''' This will, in general, be wrong '''
        return self.decodeTable[opcode][4]