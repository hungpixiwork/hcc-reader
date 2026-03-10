"""
HC Parser - Read MetaTrader 5 .hc (cache) files.

File format (reverse-engineered from MT5 Build 4620+):

    Header: 502 bytes
      [0x00]  uint32   header_size (always 502 = 0x1F6)
      [0x04]  UTF-16LE copyright string "Copyright 2000-20XX, MetaQuotes Ltd."
      [0x84]  UTF-16LE type string "HistoryCache"
      [0xA4]  uint32   last_sync_timestamp
      [0xAC]  uint32   num_records (N)
      [0x1AC] uint32   num_records (N) - duplicated

    Index Section @ 0x1B0:
      N x int64 timestamps (8 bytes each, Unix epoch seconds)

    Data Section @ (0x1B0 + N*8):
      uint32   num_records (N) - repeated
      N x float64 values per column (Open, High, Low, Close, TickVolume, Spread, RealVolume)

    Columns are stored in columnar format (all Opens, then all Highs, etc.)
"""

import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd


# --- Constants ---
HEADER_SIZE = 502
HEADER_MAGIC = 0x1F6
INDEX_START = 0x1B0
RECORD_COUNT_OFFSET = 0xAC
RECORD_COUNT_OFFSET_2 = 0x1AC
COPYRIGHT_OFFSET = 0x04
TYPE_OFFSET = 0x84
SYMBOL_OFFSET = 0xA4


def _read_utf16le_string(data: bytes, offset: int, max_len: int = 64) -> str:
    """Read a null-terminated UTF-16LE string from binary data."""
    end = offset
    while end < offset + max_len * 2 and end + 1 < len(data):
        if data[end] == 0 and data[end + 1] == 0:
            break
        end += 2
    return data[offset:end].decode("utf-16-le", errors="replace")


def parse_hc_header(filepath: str) -> dict:
    """
    Parse the header of a .hc file and return metadata.

    Args:
        filepath: Path to the .hc file.

    Returns:
        Dictionary with keys: magic, copyright, type, num_records, sync_timestamp
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(path, "rb") as f:
        header = f.read(HEADER_SIZE)

    if len(header) < HEADER_SIZE:
        raise ValueError(f"File too small for HC format: {len(header)} bytes")

    magic = struct.unpack_from("<I", header, 0)[0]
    if magic != HEADER_MAGIC:
        raise ValueError(
            f"Invalid HC magic number: 0x{magic:08X} (expected 0x{HEADER_MAGIC:08X})"
        )

    copyright_str = _read_utf16le_string(header, COPYRIGHT_OFFSET)
    type_str = _read_utf16le_string(header, TYPE_OFFSET, max_len=32)
    num_records = struct.unpack_from("<I", header, RECORD_COUNT_OFFSET)[0]
    sync_ts = struct.unpack_from("<I", header, 0xA4)[0]

    # Detect timeframe from filename
    timeframe = path.stem  # e.g. "Daily", "H1", "M5"

    return {
        "magic": magic,
        "copyright": copyright_str,
        "type": type_str,
        "num_records": num_records,
        "sync_timestamp": sync_ts,
        "timeframe": timeframe,
        "filepath": str(path.absolute()),
    }


def read_hc(filepath: str, as_dataframe: bool = True) -> pd.DataFrame:
    """
    Read a MetaTrader 5 .hc (cache) file into a pandas DataFrame.

    The .hc files are pre-computed timeframe caches stored in:
    terminal/bases/server/history/<symbol>/cache/<Timeframe>.hc

    Args:
        filepath: Path to the .hc file.
        as_dataframe: If True, return pandas DataFrame (default).

    Returns:
        DataFrame with columns: datetime, open, high, low, close,
        tick_volume, spread, real_volume

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file format is invalid.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(path, "rb") as f:
        data = f.read()

    file_size = len(data)
    if file_size < HEADER_SIZE:
        raise ValueError(f"File too small: {file_size} bytes")

    # Validate header
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic != HEADER_MAGIC:
        raise ValueError(f"Invalid magic: 0x{magic:08X}")

    num_records = struct.unpack_from("<I", data, RECORD_COUNT_OFFSET)[0]
    if num_records == 0:
        return pd.DataFrame(
            columns=["datetime", "open", "high", "low", "close",
                      "tick_volume", "spread", "real_volume"]
        )

    # Verify duplicate record count
    num_records_2 = struct.unpack_from("<I", data, RECORD_COUNT_OFFSET_2)[0]
    if num_records != num_records_2:
        # Use the smaller as safeguard
        num_records = min(num_records, num_records_2)

    # --- Parse Timestamp Index ---
    ts_section_start = INDEX_START
    ts_section_size = num_records * 8
    ts_section_end = ts_section_start + ts_section_size

    if ts_section_end > file_size:
        raise ValueError(
            f"Timestamp section exceeds file: need {ts_section_end}, have {file_size}"
        )

    timestamps = []
    for i in range(num_records):
        offset = ts_section_start + i * 8
        ts = struct.unpack_from("<q", data, offset)[0]
        timestamps.append(datetime.fromtimestamp(ts, tz=timezone.utc))

    # --- Parse Data Section (Columnar Blocks) ---
    # Layout: [count(4)] [Col0 N×8] [count(4)] [Col1 N×8] ...
    # Each block = uint32 count marker + N × float64 values
    n = num_records
    block_size = 4 + n * 8  # 4-byte count + data

    column_names = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    columns = {}

    block_offset = ts_section_end  # After timestamp index

    for col_name in column_names:
        if block_offset + 4 > file_size:
            break

        block_count = struct.unpack_from("<I", data, block_offset)[0]

        # Validate: count should match expected or be 0 (end of data)
        if block_count == 0 and col_name not in ("tick_volume", "spread", "real_volume"):
            break

        data_offset = block_offset + 4
        if data_offset + n * 8 > file_size:
            break

        values = []
        for i in range(n):
            val = struct.unpack_from("<d", data, data_offset + i * 8)[0]
            values.append(val)

        # Convert volume/spread to int
        if col_name in ("tick_volume", "spread", "real_volume"):
            values = [int(v) for v in values]

        columns[col_name] = values
        block_offset += block_size  # Jump to next block

    # Build DataFrame
    df = pd.DataFrame(columns)
    df.insert(0, "datetime", timestamps)

    return df
