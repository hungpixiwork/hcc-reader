"""
Scanner - Auto-detect MetaTrader 5 terminal directories and available data.

Scans the standard MT5 data location:
  %APPDATA%/MetaQuotes/Terminal/<terminal_id>/bases/<server>/history/<symbol>/
"""

import os
from pathlib import Path
from typing import Optional


def _get_mt5_base_dir() -> Path:
    """Get the MetaQuotes terminal base directory."""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        raise EnvironmentError("APPDATA environment variable not set")
    return Path(appdata) / "MetaQuotes" / "Terminal"


def scan_terminals(base_dir: Optional[str] = None) -> list:
    """
    Scan for all MT5 terminal installations.

    Args:
        base_dir: Custom base directory. If None, uses default APPDATA location.

    Returns:
        List of dicts with keys: terminal_id, path, servers
    """
    if base_dir:
        root = Path(base_dir)
    else:
        root = _get_mt5_base_dir()

    if not root.exists():
        return []

    terminals = []
    for terminal_dir in root.iterdir():
        if not terminal_dir.is_dir():
            continue

        bases_dir = terminal_dir / "bases"
        if not bases_dir.exists():
            continue

        servers = []
        for server_dir in bases_dir.iterdir():
            if server_dir.is_dir():
                history_dir = server_dir / "history"
                if history_dir.exists():
                    servers.append({
                        "name": server_dir.name,
                        "history_path": str(history_dir),
                    })

        if servers:
            terminals.append({
                "terminal_id": terminal_dir.name,
                "path": str(terminal_dir),
                "servers": servers,
            })

    return terminals


def scan_symbols(history_path: str) -> list:
    """
    Scan available symbols in a history directory.

    Args:
        history_path: Path to the history directory (e.g. .../bases/<server>/history/)

    Returns:
        List of dicts with keys: symbol, path, hcc_files, hc_files
    """
    root = Path(history_path)
    if not root.exists():
        return []

    symbols = []
    for symbol_dir in sorted(root.iterdir()):
        if not symbol_dir.is_dir():
            continue

        hcc_files = sorted(symbol_dir.glob("*.hcc"))
        cache_dir = symbol_dir / "cache"
        hc_files = sorted(cache_dir.glob("*.hc")) if cache_dir.exists() else []

        if hcc_files or hc_files:
            symbols.append({
                "symbol": symbol_dir.name,
                "path": str(symbol_dir),
                "hcc_files": [
                    {"year": f.stem, "path": str(f), "size": f.stat().st_size}
                    for f in hcc_files
                ],
                "hc_files": [
                    {"timeframe": f.stem, "path": str(f), "size": f.stat().st_size}
                    for f in hc_files
                ],
            })

    return symbols


def scan_timeframes(symbol_path: str) -> list:
    """
    Scan available timeframes for a symbol.

    Args:
        symbol_path: Path to a symbol directory.

    Returns:
        List of dicts with keys: timeframe, path, size, type (hcc/hc)
    """
    root = Path(symbol_path)
    if not root.exists():
        return []

    timeframes = []

    # HCC files (M1 raw data, named by year)
    for hcc_file in sorted(root.glob("*.hcc")):
        timeframes.append({
            "timeframe": f"M1 ({hcc_file.stem})",
            "path": str(hcc_file),
            "size": hcc_file.stat().st_size,
            "type": "hcc",
        })

    # HC cache files
    cache_dir = root / "cache"
    if cache_dir.exists():
        tf_order = {"M1": 1, "M5": 5, "M15": 15, "M30": 30,
                    "H1": 60, "H4": 240, "Daily": 1440, "Weekly": 10080}
        hc_files = sorted(
            cache_dir.glob("*.hc"),
            key=lambda f: tf_order.get(f.stem, 99999)
        )
        for hc_file in hc_files:
            timeframes.append({
                "timeframe": hc_file.stem,
                "path": str(hc_file),
                "size": hc_file.stat().st_size,
                "type": "hc",
            })

    return timeframes
