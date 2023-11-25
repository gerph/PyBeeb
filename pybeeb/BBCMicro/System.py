'''
Created on 16 Oct 2011

@author: Chris
'''
import OS
import PagedROM
import Sheila

class Beeb(object):
    def __init__(self, cpu):
        self.os = OS.MOS()
        self.pagedROM = PagedROM.PagedROM()
        self.sheila = Sheila.Sheila(self)

        cpu.memory.map( (OS.BASE, OS.TOP), self.os)
        cpu.memory.map( (PagedROM.BASE, PagedROM.TOP), self.pagedROM)
        cpu.memory.map( (Sheila.BASE, Sheila.TOP), self.sheila)

        self.cpu = cpu
        self.cpu.reset()
        self.setPagedROM(0)
#        self.cpu.memory.writeByte(0x028c, 15)

    def setPagedROM(self, pagedRom):
        self.pagedROM.setPagedROM(pagedRom)

    def tick(self):
        self.cpu.dispatch()
