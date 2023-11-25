#!/usr/bin/env python
'''
Created on 12 Oct 2011

@author: chris.whitworth
'''

import os

import pybeeb.Disassembler
import ROMs.TestData as TestData

DecodeFilename = os.path.join(os.path.dirname(pybeeb.__file__), "insts.csv")

def main():
    disassembler = pybeeb.Disassembler.Disassembler(DecodeFilename)
    disassembler.disassemble(TestData.testROM1)


if __name__ == '__main__':
    main()