import struct
import sys

filepath = r'C:\Users\ppnh1\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06\bases\Exness-MT5Real39\history\XAUUSD\2026.hcc'

with open(filepath, 'rb') as f:
    data = f.read()

print(f'Total file size: {len(data)} bytes')
print()

# Hex dump first 512 bytes
print('=== HEX DUMP (first 512 bytes) ===')
for offset in range(0, min(512, len(data)), 16):
    chunk = data[offset:offset+16]
    hex_part = ' '.join(f'{b:02x}' for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f'{offset:04x}: {hex_part:<48s} |{ascii_part}|')

print()

# Try to interpret the header
print('=== HEADER ANALYSIS ===')
# First 4 bytes as int32
val = struct.unpack_from('<I', data, 0)[0]
print(f'Offset 0: uint32 = {val} (0x{val:08x})')

val = struct.unpack_from('<H', data, 0)[0]
print(f'Offset 0: uint16 = {val}')

# Check for common patterns
print()
print('=== TRYING DIFFERENT STRUCT INTERPRETATIONS ===')

# Try reading as header + records
# Common MT5 record: datetime(8) + open(8) + high(8) + low(8) + close(8) + volume(8) + spread(4) + real_volume(8) = 60 bytes
# Or: datetime(8) + open(8) + high(8) + low(8) + close(8) + tick_volume(8) + spread(4) + real_volume(8) = 60 bytes

# Try different header sizes and record sizes
for header_size in [0, 4, 8, 16, 20, 24, 28, 32, 48, 64, 128, 148, 192, 256]:
    remaining = len(data) - header_size
    for record_size in [44, 48, 52, 56, 60, 64, 68, 72, 76, 80]:
        if remaining > 0 and remaining % record_size == 0:
            num_records = remaining // record_size
            if num_records > 0 and num_records < 10000:
                print(f'  header={header_size}, record_size={record_size}, num_records={num_records}')

print()

# Try to parse assuming zlib compression
import zlib
print('=== COMPRESSION CHECK ===')
# Check for zlib header (78 01, 78 5E, 78 9C, 78 DA)
for i in range(min(256, len(data))):
    if data[i] == 0x78 and i+1 < len(data) and data[i+1] in (0x01, 0x5E, 0x9C, 0xDA):
        print(f'  Possible zlib header at offset {i}: {data[i]:02x} {data[i+1]:02x}')
        try:
            decompressed = zlib.decompress(data[i:])
            print(f'  -> Decompressed {len(decompressed)} bytes!')
            # Dump first 256 bytes of decompressed data
            for offset in range(0, min(256, len(decompressed)), 16):
                chunk = decompressed[offset:offset+16]
                hex_part = ' '.join(f'{b:02x}' for b in chunk)
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                print(f'  {offset:04x}: {hex_part:<48s} |{ascii_part}|')
        except Exception as e:
            print(f'  -> Decompression failed: {e}')

# Check if entire file is zlib compressed
try:
    decompressed = zlib.decompress(data)
    print(f'Entire file decompresses to {len(decompressed)} bytes')
except:
    print('Entire file is NOT zlib compressed')

# Try with different skip sizes
for skip in range(0, 32):
    try:
        decompressed = zlib.decompress(data[skip:])
        print(f'Decompresses from offset {skip} to {len(decompressed)} bytes')
        break
    except:
        pass

print()
print('=== STRING SEARCH ===')
# Look for any readable strings
i = 0
while i < len(data):
    if 32 <= data[i] < 127:
        j = i
        while j < len(data) and 32 <= data[j] < 127:
            j += 1
        if j - i >= 4:
            print(f'  Offset {i}: "{data[i:j].decode("ascii")}"')
        i = j
    else:
        i += 1
