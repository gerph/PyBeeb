'''
Created on 12 Oct 2011

@author: chris.whitworth
'''
from struct import unpack

class InvalidAddressException(Exception):
    def __init__(self, address):
        self.address = address

    def __repr__(self):
        return "Invalid address: %s" % hex(self.address)

class ValueOutOfRange(Exception):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "Value out of range: %s" % hex(self.value)

class Memory(object):
    class Map(object):
        def __init__(self, range, callback):
            self.range = range
            self.callback = callback

        def base(self):
            return self.range[0]

        def end(self):
            return self.range[1]

        def isInMap(self, address):
            return True if address >= self.base() and address < self.end()  else False

    MEMORYSIZE = 64 * 1024
    def __init__(self):
        self.memory = bytearray(self.MEMORYSIZE)
        self.protection = bytearray(self.MEMORYSIZE)
        self.maps = []

    def map(self, range, callback):
        self.maps.append( self.Map(range, callback) )

    def unmap(self, range):
        raise BaseException("Cannae do this")

    def getMapFor(self, address):
        maps = [ map for map in self.maps if map.isInMap(address) ]
        if len(maps) != 0:
            return maps[-1]
        else:
            return None

    def readByte(self, address):
        # TODO - add memory mapping
        if address < 0 or address > 0xffff:
            raise InvalidAddressException(address)

        map = self.getMapFor(address)

        if map != None:
            base = map.base()
            mappedDevice = map.callback
            readByte = mappedDevice.readByte(address - base)
        else:
            readByte = self.memory[address]

        #print "Read byte %s from %s" % (hex(readByte) , hex(address))
        return readByte

    def writeByte(self, address, value):
        # TODO - add memory mapping
        if address < 0 or address > 0xffff:
            raise InvalidAddressException(address)

        if value < 0 or value > 0xff:
            raise ValueOutOfRange(value)

        map = self.getMapFor(address)
        if map != None:
            base = map.base()
            mappedDevice = map.callback
            mappedDevice.writeByte(address - base, value)
        else:
            self.memory[address] = value

    def readSignedByte(self, address):
        b = self.readByte(address)
        return unpack("b", chr(b))[0]

    def readWord(self, address):
        return self.readByte(address) + (self.readByte(address + 1) << 8)