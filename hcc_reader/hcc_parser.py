"""
HCC Parser - Read MetaTrader 5 .hcc (compressed history) files.

File format (reverse-engineered from MT5 Build 4620+):

    Header: 502 bytes
      [0x00]  uint32   header_size (always 502 = 0x1F6)
      [0x04]  UTF-16LE copyright string
      [0x84]  UTF-16LE "History"
      [0xA4]  UTF-16LE symbol name (e.g. "XAUUSDm")

    Block Index @ ~0xE4:
      Variable-length block directory entries

    Data Blocks:
      M1 OHLCV records, 60 bytes each:
        int64   timestamp     (Unix epoch seconds)
        float64 open
        float64 high
        float64 low
        float64 close
        int64   tick_volume
        int32   spread
        int32   real_volume

    Note: Data is stored as 1-minute (M1) candles.
    The .hcc file contains ALL minute data for one year.
"""

import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd


# --- Constants ---
HEADER_SIZE = 502
HEADER_MAGIC = 0x1F6
M1_RECORD_SIZE = 60
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


def parse_hcc_header(filepath: str) -> dict:
    """
    Parse the header of a .hcc file and return metadata.

    Args:
        filepath: Path to the .hcc file.

    Returns:
        Dictionary with keys: magic, copyright, type, symbol, year, filepath
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(path, "rb") as f:
        header = f.read(HEADER_SIZE)

    if len(header) < HEADER_SIZE:
        raise ValueError(f"File too small for HCC format: {len(header)} bytes")

    magic = struct.unpack_from("<I", header, 0)[0]
    if magic != HEADER_MAGIC:
        raise ValueError(
            f"Invalid HCC magic: 0x{magic:08X} (expected 0x{HEADER_MAGIC:08X})"
        )

    copyright_str = _read_utf16le_string(header, COPYRIGHT_OFFSET)
    type_str = _read_utf16le_string(header, TYPE_OFFSET, max_len=32)
    symbol_str = _read_utf16le_string(header, SYMBOL_OFFSET, max_len=32)

    # Year from filename
    year = path.stem  # e.g. "2024"

    return {
        "magic": magic,
        "copyright": copyright_str,
        "type": type_str,
        "symbol": symbol_str,
        "year": year,
        "filepath": str(path.absolute()),
        "file_size": path.stat().st_size,
    }


def _find_m1_records(data: bytes) -> list:
    """
    Scan binary data to find ALL M1 OHLCV records across multiple blocks.

    HCC files contain multiple data blocks scattered throughout the file.
    Each block is a contiguous sequence of 60-byte M1 records.
    """
    all_records = []
    min_ts = 946684800   # 2000-01-01
    max_ts = 1893456000  # 2030-01-01
    data_len = len(data)

    scan_pos = HEADER_SIZE
    while scan_pos < data_len - M1_RECORD_SIZE:
        # Find the next valid record start
        found_start = None
        for i in range(scan_pos, min(data_len - M1_RECORD_SIZE, scan_pos + 50000), 1):
            ts = struct.unpack_from("<q", data, i)[0]
            if not (min_ts < ts < max_ts):
                continue

            o = struct.unpack_from("<d", data, i + 8)[0]
            h = struct.unpack_from("<d", data, i + 16)[0]
            l = struct.unpack_from("<d", data, i + 24)[0]
            c = struct.unpack_from("<d", data, i + 32)[0]

            if not (0 < o < 1_000_000 and 0 < h < 1_000_000 and
                    0 < l < 1_000_000 and 0 < c < 1_000_000):
                continue

            if not (h >= l and h >= min(o, c) * 0.9 and l <= max(o, c) * 1.1):
                continue

            # Verify next record
            if i + M1_RECORD_SIZE + 8 <= data_len:
                next_ts = struct.unpack_from("<q", data, i + M1_RECORD_SIZE)[0]
                if min_ts < next_ts < max_ts and next_ts >= ts:
                    found_start = i
                    break

        if found_start is None:
            # Try jumping ahead
            scan_pos += 50000
            if scan_pos >= data_len:
                break
            continue

        # Read contiguous records from this block
        pos = found_start
        block_records = 0
        while pos + M1_RECORD_SIZE <= data_len:
            ts = struct.unpack_from("<q", data, pos)[0]
            if not (min_ts < ts < max_ts):
                break

            o = struct.unpack_from("<d", data, pos + 8)[0]
            h = struct.unpack_from("<d", data, pos + 16)[0]
            l = struct.unpack_from("<d", data, pos + 24)[0]
            c = struct.unpack_from("<d", data, pos + 32)[0]
            tick_vol = struct.unpack_from("<q", data, pos + 40)[0]
            spread = struct.unpack_from("<i", data, pos + 48)[0]
            real_vol = struct.unpack_from("<i", data, pos + 52)[0]

            if o <= 0 or h <= 0 or l <= 0 or c <= 0:
                break

            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            all_records.append({
                "datetime": dt,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "tick_volume": int(tick_vol),
                "spread": int(spread),
                "real_volume": int(real_vol),
            })

            pos += M1_RECORD_SIZE
            block_records += 1

        scan_pos = pos + 1  # Continue scanning after this block

    # Sort by timestamp and remove duplicates
    if all_records:
        all_records.sort(key=lambda r: r["datetime"])
        # Remove duplicates based on datetime
        seen = set()
        unique = []
        for r in all_records:
            key = r["datetime"]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    return all_records


def read_hcc(filepath: str, as_dataframe: bool = True) -> pd.DataFrame:
    """
    Read a MetaTrader 5 .hcc (compressed history) file into a pandas DataFrame.

    The .hcc files contain M1 (1-minute) candle data, stored in:
    terminal/bases/server/history/<symbol>/<year>.hcc

    Args:
        filepath: Path to the .hcc file.
        as_dataframe: If True, return pandas DataFrame (default).

    Returns:
        DataFrame with columns: datetime, open, high, low, close,
        tick_volume, spread, real_volume

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file format is invalid or no data found.
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

    # Find and parse M1 records
    records = _find_m1_records(data)

    if not records:
        return pd.DataFrame(
            columns=["datetime", "open", "high", "low", "close",
                      "tick_volume", "spread", "real_volume"]
        )

    df = pd.DataFrame(records)
    return df
