"""
HCC Reader - Read MetaTrader 5 .hcc/.hc history files without MT5 terminal.

Reverse-engineered binary format parser for MT5 proprietary history files.
Supports both compressed (.hcc) and cache (.hc) formats.

Author: hungpixi (https://github.com/hungpixi)
Website: https://comarai.com
"""

__version__ = "1.0.0"
__author__ = "Pham Phu Nguyen Hung"

from hcc_reader.hc_parser import read_hc, parse_hc_header
from hcc_reader.hcc_parser import read_hcc, parse_hcc_header
from hcc_reader.scanner import scan_terminals, scan_symbols, scan_timeframes

__all__ = [
    "read_hc",
    "read_hcc",
    "parse_hc_header",
    "parse_hcc_header",
    "scan_terminals",
    "scan_symbols",
    "scan_timeframes",
]
