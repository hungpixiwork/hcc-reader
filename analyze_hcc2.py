import struct
from datetime import datetime

filepath = r'C:\Users\ppnh1\AppData\Roaming\MetaQuotes\Terminal\53785E099C927DB68A545C249CDBCE06\bases\Exness-MT5Real39\history\XAUUSD\2026.hcc'

with open(filepath, 'rb') as f:
    data = f.read()

print(f'Total file size: {len(data)} bytes')

# Header seems to be around 0x1F6 = 502 bytes based on the first uint32
# But let's explore more carefully

# The copyright string starts at offset 4 in UTF-16LE
# Let's find where the header ends

# Dump bytes around the header boundary
print('\n=== BYTES AROUND OFFSET 0x80 (128) ===')
for i in range(0x80, 0xC0, 16):
    chunk = data[i:i+16]
    hex_part = ' '.join(f'{b:02x}' for b in chunk)
    print(f'{i:04x}: {hex_part}')

# "History" at 0x84, "XAUUSD" at 0xA4
# Let's see what's after the zero padding

# Look for non-zero bytes after the strings
print('\n=== FIRST NON-ZERO AFTER HEADER STRINGS ===')
for i in range(0xA4, len(data)):
    if data[i] != 0:
        print(f'First non-zero at offset {i} (0x{i:04x}): {data[i]:02x}')
        # Dump some context
        start = max(0, i - 4)
        end = min(len(data), i + 64)
        for j in range(start, end, 16):
            chunk = data[j:j+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            print(f'{j:04x}: {hex_part}')
        break

# Try header = 502 (0x1F6) which was the first uint32
header_end = 502
print(f'\n=== DATA STARTS AT OFFSET {header_end} ===')
remaining = len(data) - header_end
print(f'Remaining data: {remaining} bytes')

# Dump first 128 bytes of data section
for i in range(header_end, min(header_end + 128, len(data)), 16):
    chunk = data[i:i+16]
    hex_part = ' '.join(f'{b:02x}' for b in chunk)
    print(f'{i:04x}: {hex_part}')

# Try to interpret as records
# MT5 MqlRates: datetime(8) + open(8) + high(8) + low(8) + close(8) + tick_vol(8) + spread(4) + real_vol(8) = 60 bytes
record_size = 56  # header=192, rec=56 gives 267 records
print(f'\n=== TRYING RECORD SIZE {record_size} ===')

# Actually let's try the standard MT5 format: 60 bytes per record
# datetime(8), open(8), high(8), low(8), close(8), tick_volume(8), spread(4), real_volume(8)

# But first, let me check what structures work
# header=192 (0xC0), record=56 works (267 records, remaining = 14952)
# 15144 - 192 = 14952, 14952/56 = 267

# Let's try header=192
header_sz = 192
print(f'\n=== TRYING HEADER={header_sz}, RECORD=56 ===')
for rec_idx in range(3):
    offset = header_sz + rec_idx * 56
    chunk = data[offset:offset+56]
    
    # Try: datetime(8), open(8), high(8), low(8), close(8), tick_vol(8), spread(4) = 52
    # Or: datetime(8), open(8), high(8), low(8), close(8), tick_vol(4), spread(4), real_vol(8) = 52+4 = 56
    
    dt_val = struct.unpack_from('<q', chunk, 0)[0]
    open_p = struct.unpack_from('<d', chunk, 8)[0]
    high_p = struct.unpack_from('<d', chunk, 16)[0]
    low_p = struct.unpack_from('<d', chunk, 24)[0]
    close_p = struct.unpack_from('<d', chunk, 32)[0]
    tick_vol = struct.unpack_from('<q', chunk, 40)[0]
    spread = struct.unpack_from('<i', chunk, 48)[0]
    real_vol = struct.unpack_from('<i', chunk, 52)[0]
    
    try:
        dt = datetime.fromtimestamp(dt_val)
        print(f'  Rec {rec_idx}: dt={dt}, O={open_p:.2f}, H={high_p:.2f}, L={low_p:.2f}, C={close_p:.2f}, vol={tick_vol}, sp={spread}, rv={real_vol}')
    except:
        print(f'  Rec {rec_idx}: dt_raw={dt_val}, O={open_p:.5f}, H={high_p:.5f}, L={low_p:.5f}, C={close_p:.5f}')

# Try MqlRates standard: 60 bytes
header_sz = 24
rec_sz = 60
print(f'\n=== TRYING HEADER={header_sz}, RECORD={rec_sz} ===')
for rec_idx in range(3):
    offset = header_sz + rec_idx * rec_sz
    chunk = data[offset:offset+rec_sz]
    
    dt_val = struct.unpack_from('<q', chunk, 0)[0]
    open_p = struct.unpack_from('<d', chunk, 8)[0]
    high_p = struct.unpack_from('<d', chunk, 16)[0]
    low_p = struct.unpack_from('<d', chunk, 24)[0]
    close_p = struct.unpack_from('<d', chunk, 32)[0]
    tick_vol = struct.unpack_from('<q', chunk, 40)[0]
    spread = struct.unpack_from('<i', chunk, 48)[0]
    real_vol = struct.unpack_from('<q', chunk, 52)[0]
    
    try:
        dt = datetime.fromtimestamp(dt_val)
        print(f'  Rec {rec_idx}: dt={dt}, O={open_p:.2f}, H={high_p:.2f}, L={low_p:.2f}, C={close_p:.2f}, vol={tick_vol}, sp={spread}, rv={real_vol}')
    except:
        print(f'  Rec {rec_idx}: dt_raw={dt_val}, O={open_p:.5f}, H={high_p:.5f}, L={low_p:.5f}, C={close_p:.5f}')

# Try bigger header
for header_sz in [0x1F6]:
    remaining = len(data) - header_sz
    print(f'\n=== TRYING HEADER=0x{header_sz:x} ({header_sz}) ===')
    print(f'Remaining: {remaining} bytes')
    
    # Dump first bytes
    for i in range(header_sz, min(header_sz + 128, len(data)), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        print(f'{i:04x}: {hex_part}')
    
    # Try record sizes
    for rec_sz in [44, 48, 52, 56, 60, 64, 68, 72]:
        if remaining % rec_sz == 0:
            n = remaining // rec_sz
            print(f'  rec_sz={rec_sz} -> {n} records')
            
            # Try first record
            chunk = data[header_sz:header_sz+rec_sz]
            dt_val = struct.unpack_from('<q', chunk, 0)[0]
            open_p = struct.unpack_from('<d', chunk, 8)[0]
            high_p = struct.unpack_from('<d', chunk, 16)[0]
            low_p = struct.unpack_from('<d', chunk, 24)[0]
            close_p = struct.unpack_from('<d', chunk, 32)[0]
            
            try:
                dt = datetime.fromtimestamp(dt_val)
                print(f'    First: dt={dt}, O={open_p:.2f}, H={high_p:.2f}, L={low_p:.2f}, C={close_p:.2f}')
            except:
                print(f'    First: dt_raw={dt_val}, O={open_p:.5f}, H={high_p:.5f}, L={low_p:.5f}, C={close_p:.5f}')
