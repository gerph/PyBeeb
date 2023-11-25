#!/usr/bin/env python
'''
Created on 12 Oct 2011

@author: chris.whitworth
'''
import os
import sys
import pybeeb.CPU.Memory as Memory
import pybeeb.CPU.Registers as Registers
import pybeeb.CPU.AddressDispatcher as AddressDispatcher
import pybeeb.CPU.Writeback as Writeback
import pybeeb.CPU.ExecutionUnit as ExecutionUnit
import pybeeb.CPU.Dispatch as Dispatch
import pybeeb.CPU.InstructionDecoder as Decoder
import pybeeb.Debugging.Combiner
import pybeeb.Debugging.Writeback
import pybeeb.Debugging.ExecutionUnit
import pybeeb.BBCMicro.System
import pybeeb

DecodeFilename = os.path.join(os.path.dirname(pybeeb.__file__), "insts.csv")


class BBC(object):
    def __init__(self, pcTrace = False, verbose = False):
        self.mem = Memory.Memory()
        self.reg = Registers.RegisterBank()
        addrDispatch = AddressDispatcher.AddressDispatcher(self.mem, self.reg)

        execDispatch = ExecutionUnit.ExecutionDispatcher(self.mem,self.reg)
        execLogger = pybeeb.Debugging.ExecutionUnit.LoggingExecutionUnit()
        combinedExec = pybeeb.Debugging.Combiner.Dispatcher( (execLogger, execDispatch) )

        writebackDispatch = Writeback.Dispatcher(self.mem,self.reg)
        writebackLogger = pybeeb.Debugging.Writeback.LoggingDispatcher()
        combinedWriteback = pybeeb.Debugging.Combiner.Dispatcher( (writebackLogger, writebackDispatch) )

        decoder = Decoder.Decoder(DecodeFilename)

        self.pcTrace = pcTrace
        self.verbose = verbose

        dispatch = None
        if verbose:
            dispatch = Dispatch.Dispatcher(decoder, addrDispatch,
                                           combinedExec, combinedWriteback,
                                           self.mem, self.reg)
        else:
            dispatch = Dispatch.Dispatcher(decoder, addrDispatch,
                                           execDispatch, writebackDispatch,
                                           self.mem, self.reg)

        self.bbc = pybeeb.BBCMicro.System.Beeb(dispatch)

    def go(self, syscalls):
        instr = 0

        while True:
            if self.pcTrace:
                print "%s: PC: %s" % (instr, hex(self.reg.pc))
            instr += 1

            if not self.pcTrace and not self.verbose:
                if self.reg.pc in syscalls.keys():
                    syscalls[self.reg.pc](self.reg, self.mem)

            self.bbc.tick()

            if self.verbose:
                self.reg.status()

def OS_WRCH(reg,mem): sys.stdout.write(chr(reg.a))
def OS_RDCH(reg,mem): print "OS_RDCH" # Could inject keypresses here maybe?

if __name__ == "__main__":
    OS_WRCH_LOC = 0xe0a4
    OS_RDCH_LOC = 0xdec5
    syscalls = { OS_WRCH_LOC : OS_WRCH,
                 OS_RDCH_LOC : OS_RDCH }
    bbc = BBC()
    bbc.go(syscalls)
