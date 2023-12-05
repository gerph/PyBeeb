#!/usr/bin/env python

import unittest
import pybeeb.CPU.Memory


class MockMapper(object):
    def __init__(self):
        self.lastByteRead = None
        self.lastByteWritten = (None, None)

    def readByte(self, address):
        self.lastByteRead = address
        return 0

    def writeByte(self, address, value):
        self.lastByteWritten = (address, value)

class MemoryTestsSimple(unittest.TestCase):
    def setUp(self):
        self.mem = pybeeb.CPU.Memory.Memory()

    def test_zeroOnReset(self):
        for address in range(self.mem.MEMORYSIZE):
            self.assertEqual(self.mem.readByte(address), 0)

    def test_writeEveryByte(self):
        for address in range(self.mem.MEMORYSIZE):
            self.mem.writeByte(address, 1)
            self.assertEqual(self.mem.readByte(address), 1)

class MappingTestSimple(unittest.TestCase):
    def setUp(self):
        self.mem = pybeeb.CPU.Memory.Memory()
        self.mapper = MockMapper()
        self.mem.map( (0, 0x100), self.mapper)

    def test_readInRange(self):
        for address in range(0x100):
            self.mem.readByte(address)
            self.assertEqual(self.mapper.lastByteRead, address)

    def test_writeInRange(self):
        for address in range(0x100):
            self.mem.writeByte(address, address ^ 0xff)
            self.assertEqual(self.mapper.lastByteWritten, (address, address ^ 0xff))

    def test_readOutOfRange(self):
        for address in range(0x100, self.mem.MEMORYSIZE):
            self.mem.readByte(address)
            self.assertEqual(self.mapper.lastByteRead, None)

    def test_writeOutOfRange(self):
        for address in range(0x100, self.mem.MEMORYSIZE):
            self.mem.writeByte(address, (address & 0xff) ^ 0xff)
            self.assertEqual(self.mapper.lastByteWritten, (None, None))

class OverlaidMappingTests(unittest.TestCase):
    def setUp(self):
        self.mem = pybeeb.CPU.Memory.Memory()

        self.firstMapper = MockMapper()
        self.secondMapper = MockMapper()

        self.mem.map( (0, 0x200), self.firstMapper)
        self.mem.map( (0x100, 0x300), self.secondMapper)

    def test_readInFirstMap(self):
        for address in range(0, 0x100):
            self.mem.readByte(address)
            self.assertEqual(self.firstMapper.lastByteRead, address)
            self.assertEqual(self.secondMapper.lastByteRead, None)

    def test_writeInFirstMap(self):
        for address in range(0, 0x100):
            self.mem.writeByte(address, address ^ 0xff)
            self.assertEqual(self.firstMapper.lastByteWritten, (address, address ^ 0xff))
            self.assertEqual(self.secondMapper.lastByteWritten, (None, None))

    def test_readInSecondMapOverlaidOnFirstMap(self):
        for address in range(0x100, 0x200):
            self.mem.readByte(address)
            self.assertEqual(self.firstMapper.lastByteRead, None)
            self.assertEqual(self.secondMapper.lastByteRead, address - 0x100)

    def test_writeInSecondMapOverlaidOnFirstMap(self):
        for address in range(0x100, 0x200):
            self.mem.writeByte(address, (address & 0xff) ^ 0xff)
            self.assertEqual(self.firstMapper.lastByteWritten, (None, None))
            self.assertEqual(self.secondMapper.lastByteWritten, (address - 0x100, (address & 0xff) ^ 0xff))

    def test_readInSecondMap(self):
        for address in range(0x200, 0x300):
            self.mem.readByte(address)
            self.assertEqual(self.firstMapper.lastByteRead, None)
            self.assertEqual(self.secondMapper.lastByteRead, address - 0x100)

    def test_writeInSecondMap(self):
        for address in range(0x200, 0x300):
            self.mem.writeByte(address, (address & 0xff) ^ 0xff)
            self.assertEqual(self.firstMapper.lastByteWritten, (None, None))
            self.assertEqual(self.secondMapper.lastByteWritten, (address - 0x100, (address & 0xff) ^ 0xff))


def main():
    unittest.main()


if __name__ == '__main__':
    main()
