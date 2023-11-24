'''
Created on 14 Oct 2011

@author: chris.whitworth
'''

class Dispatcher(object):
    def __init__(self,memory,registers):
        self.mem = memory
        self.registers = registers

    def A(self, value, location):
        self.registers.a = value

    def X(self, value, location):
        self.registers.x = value

    def Y(self, value, location):
        self.registers.y = value

    def memory(self, value, location):
        self.mem.writeByte(location, value)

    def PC(self, value, location):
        self.registers.nextPC = value

    def SP(self, value, location):
        self.registers.sp = value

    def PS(self, value, location):
        self.registers.setPS(value)

    def NW(self, value, location):
        pass