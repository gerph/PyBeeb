'''
Created on 12 Oct 2011

@author: chris.whitworth
'''

import Disassembler
import ROMs.TestData as TestData

DecoderTablePath = "insts.csv"

def main():
    disassembler = Disassembler.Disassembler(DecoderTablePath)
    disassembler.disassemble(TestData.testROM1)


if __name__ == '__main__':
    main()