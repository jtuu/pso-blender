class Decoder:
    def __init__(self, compressed_buf: bytes):
        self._cmds = 0
        self._rem = 0
        self._read_cursor = 0
        self.compressed_buf = compressed_buf
        self.decompressed_buf = bytearray()

    def _read_bit(self) -> bool:
        if self._rem == 0:
            self._cmds = self.compressed_buf[self._read_cursor]
            self._read_cursor += 1
            self._rem = 8
        ret = self._cmds & 1
        self._cmds >>= 1
        self._rem -= 1
        return ret != 0
    
    def decompress(self):
        while True:
            if self._read_bit():
                literal = self.compressed_buf[self._read_cursor]
                self._read_cursor += 1
                self.decompressed_buf.append(literal)
                continue
            if self._read_bit():
                offset = self.compressed_buf[self._read_cursor] | (self.compressed_buf[self._read_cursor + 1] << 8)
                self._read_cursor += 2
                if offset == 0:
                    break
                size = offset & 0b111
                offset >>= 3
                if size == 0:
                    size = self.compressed_buf[self._read_cursor] + 1
                    self._read_cursor += 1
                else:
                    size += 2
                offset |= -8192
            else:
                flag = 1 if self._read_bit() else 0
                bit = 1 if self._read_bit() else 0
                size = (bit | (flag << 1)) + 2
                offset = self.compressed_buf[self._read_cursor]
                self._read_cursor += 1
                offset |= -256
            for _ in range(size):
                self.decompressed_buf.append(self.decompressed_buf[offset])


def decompress(compressed_buf: bytearray) -> bytearray:
    dec = Decoder(compressed_buf)
    dec.decompress()
    return dec.decompressed_buf
