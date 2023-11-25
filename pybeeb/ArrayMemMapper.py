'''
Created on 13 Oct 2011

@author: chris.whitworth
'''

class Mapper(object):
    def __init__(self, data):
        self.data = data

    def readByte(self, address):
        return self.data[address]

    def writeByte(self, address, value):
        self.data[address] = value