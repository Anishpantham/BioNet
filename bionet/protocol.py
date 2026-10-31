"""Version 1 wire codec; CRC covers header and payload."""
import struct
import zlib
MAX_SEQUENCE = (1 << 64) - 1
MAX_FILE_SIZE = 1 << 40
HEADER = struct.Struct('!4sBB16sQH')
START, START_ACK, DATA, ACK, FIN, FIN_ACK, ERROR = range(1, 8)

def encode(kind, session, seq=0, payload=b''):
    if type(seq) is not int or type(kind) is not int or not 0 <= seq <= MAX_SEQUENCE or len(payload) > 1200 or len(session) != 16 or kind not in range(1, 8):
        raise ValueError('invalid packet')
    body = HEADER.pack(b'BNET', 1, kind, session, seq, len(payload)) + payload
    return body + struct.pack('!I', zlib.crc32(body))

def decode(raw):
    if len(raw) < HEADER.size + 4:
        raise ValueError('short packet')
    magic, version, kind, session, seq, length = HEADER.unpack(raw[:HEADER.size])
    if magic != b'BNET' or version != 1 or kind not in range(1, 8) or length > 1200 or len(raw) != HEADER.size + length + 4:
        raise ValueError('invalid header')
    if zlib.crc32(raw[:-4]) != struct.unpack('!I', raw[-4:])[0]:
        raise ValueError('CRC mismatch')
    return kind, session, seq, raw[HEADER.size:-4]
