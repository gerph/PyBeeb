'''
Created on 13 Oct 2011

@author: chris.whitworth
'''

testROM1 = [
    0xad, 0x00, 0xff,    # LDA &FF00    (a=0xad)
    0x6c, 0x06, 0xff,    # JMP (&FF06)
    0x1b, 0xff,        # (&FF1B)
    0x49, 0xff,        # EOR #255
    0x60,            # RTS
    0xf2,            # NXX (NOP)
    0xa9, 7,        # LDA #7
    0x48,            # PHA
    0xa9, 2,        # LDA #2
    0x48,            # PHA
    0xba,            # TSX
    0xe8,            # INX
    0x9a,            # TXS
    0x68,            # PLA
    0xa8,            # TAY
    0x8c, 0x00, 0x02,    # STY &200
    0x40,            # RTI
    0x29, 0x0f,        # AND #&0F    (a=0x0d)
    0x0a,            # ASL A    (a=0x1a)
    0x0a,            # ASL A    (a=0x34)
    0x0a,            # ASL A    (a=0x68)
    0x0a,            # ASL A    (a=0xd0)
    0x0a,            # ASL A    (a=0xa0  c=1)
    0xb0, 2,        # BCS +2    (to the STA)
    0xea, 0xea,        # NOP:NOP
    0x85, 0xff,        # STA &FF
    0x18,            # CLC
    0xca, 0x88,        # DEX : DEY
    0xa9, 1,        # LDA #1
    0x20, 0x08, 0xff,    # JSR &FF08
    0xd6, 0,        # DEC &00, X
    0xa5, 0xff,        # LDA &FF
    0x2c, 0x01, 0xff,    # BIT &FF01    (z = 1)
    0xf0, 4,        # BEQ +4
    0x0,            # BRK
    0x38,            # SEC
    0xb0, 2,        # BCS +2 (HCF)
    0xf0, 0xfa,        # BEQ -6 (to the BRK)
    0xff ]            # HCF

testROM2 = [
    0x69, 0x34, # ADC #&34
    0x65, 0x34, # ADC &34 (zp)
    0x75, 0x34, # ADC &34, X
    0x6d, 0x34, 0x00, # ADC &0034
    0x7d, 0x34, 0x00, # ADC &0034, X
    0x79, 0x34, 0x00, # ADC &0034, Y

    ]