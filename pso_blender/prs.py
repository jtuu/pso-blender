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


class Encoder:
    def __init__(self, uncompressed_buf: bytearray):
        self._max_offset = 0x1fff
        self._bit_position = 0
        self._byte_position = 0
        self._read_cursor = 0
        self._uncompressed_buf = uncompressed_buf
        self._uncompressed_len = len(uncompressed_buf)
        self._compressed_buf = bytearray()

    def _lz77_longest_match(self):
        max_len = 0x100
        best_offset = 0
        best_len = 0
        cur_len = 0
        min_pos = max(self._read_cursor - self._max_offset, 0)
        if self._read_cursor + max_len + 4 >= self._uncompressed_len:
            for i in range(self._read_cursor - 1, min_pos, -1):
                if self._uncompressed_buf[i] == self._uncompressed_buf[self._read_cursor]:
                    cur_len = 1
                    while self._read_cursor + cur_len < self._uncompressed_len and self._uncompressed_buf[i + cur_len] == self._uncompressed_buf[self._read_cursor + cur_len]:
                        cur_len += 1
                    if cur_len > max_len:
                        cur_len = max_len
                        best_len = cur_len
                        best_offset = i - self._read_cursor
                        #goto(hell)
                    elif cur_len > best_len:
                        best_len = cur_len
                        best_offset = i - self._read_cursor

    def compress(self):
        while self._read_cursor < self._uncompressed_len:
            self._lz77_longest_match()
