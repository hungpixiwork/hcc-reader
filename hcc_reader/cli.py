"""
CLI - Command-line interface for HCC Reader.

Usage:
    hcc-reader scan                     Scan MT5 terminals
    hcc-reader info <path>              Show file metadata
    hcc-reader read <path>              Read and display data
    hcc-reader export <path> -f csv     Export to CSV/JSON
"""

import sys
from pathlib import Path

import click
import pandas as pd

from hcc_reader.hc_parser import read_hc, parse_hc_header
from hcc_reader.hcc_parser import read_hcc, parse_hcc_header
from hcc_reader.scanner import scan_terminals, scan_symbols, scan_timeframes


def _format_size(size_bytes: int) -> str:
    """Format file size to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


@click.group()
@click.version_option(version="1.0.0", prog_name="hcc-reader")
def main():
    """🔍 HCC Reader - Read MetaTrader 5 history files without MT5 terminal.

    Supports both .hcc (compressed M1 data) and .hc (timeframe cache) files.
    """
    pass


@main.command()
@click.option("--base-dir", "-d", default=None, help="Custom MetaQuotes base directory")
def scan(base_dir):
    """📂 Scan MT5 terminals and list available data."""
    click.echo("🔍 Scanning for MetaTrader 5 terminals...\n")

    terminals = scan_terminals(base_dir)

    if not terminals:
        click.echo("❌ No MT5 terminals found.")
        return

    for term in terminals:
        click.echo(f"📁 Terminal: {term['terminal_id'][:16]}...")
        click.echo(f"   Path: {term['path']}")

        for server in term["servers"]:
            click.echo(f"\n   🖥️  Server: {server['name']}")

            symbols = scan_symbols(server["history_path"])
            for sym in symbols:
                hcc_count = len(sym["hcc_files"])
                hc_count = len(sym["hc_files"])
                click.echo(f"   ├── {sym['symbol']}: {hcc_count} .hcc, {hc_count} .hc files")

                for hcc in sym["hcc_files"]:
                    click.echo(
                        f"   │   ├── 📦 {hcc['year']}.hcc ({_format_size(hcc['size'])})"
                    )
                for hc in sym["hc_files"]:
                    click.echo(
                        f"   │   └── 📊 {hc['timeframe']}.hc ({_format_size(hc['size'])})"
                    )

    click.echo(f"\n✅ Found {len(terminals)} terminal(s)")


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
def info(filepath):
    """ℹ️  Show metadata for a .hcc or .hc file."""
    path = Path(filepath)

    if path.suffix == ".hc":
        header = parse_hc_header(filepath)
        click.echo("📊 HC Cache File Info")
        click.echo(f"   Type:       {header['type']}")
        click.echo(f"   Timeframe:  {header['timeframe']}")
        click.echo(f"   Records:    {header['num_records']:,}")
        click.echo(f"   Copyright:  {header['copyright']}")
        click.echo(f"   Path:       {header['filepath']}")

    elif path.suffix == ".hcc":
        header = parse_hcc_header(filepath)
        click.echo("📦 HCC History File Info")
        click.echo(f"   Type:       {header['type']}")
        click.echo(f"   Symbol:     {header['symbol']}")
        click.echo(f"   Year:       {header['year']}")
        click.echo(f"   File size:  {_format_size(header['file_size'])}")
        click.echo(f"   Copyright:  {header['copyright']}")
        click.echo(f"   Path:       {header['filepath']}")

    else:
        click.echo(f"❌ Unsupported file type: {path.suffix}")
        click.echo("   Supported: .hcc, .hc")


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--rows", "-n", default=20, help="Number of rows to display")
@click.option("--tail", is_flag=True, help="Show last N rows instead of first N")
def read(filepath, rows, tail):
    """📖 Read and display data from a .hcc or .hc file."""
    path = Path(filepath)

    try:
        if path.suffix == ".hc":
            df = read_hc(filepath)
        elif path.suffix == ".hcc":
            df = read_hcc(filepath)
        else:
            click.echo(f"❌ Unsupported: {path.suffix}")
            return
    except Exception as e:
        click.echo(f"❌ Error reading file: {e}")
        return

    if df.empty:
        click.echo("⚠️  No data found in file.")
        return

    click.echo(f"📊 {path.name} — {len(df):,} records")
    click.echo(f"   Period: {df['datetime'].iloc[0]} → {df['datetime'].iloc[-1]}")
    click.echo()

    if tail:
        click.echo(df.tail(rows).to_string(index=False))
    else:
        click.echo(df.head(rows).to_string(index=False))

    if len(df) > rows:
        click.echo(f"\n... ({len(df) - rows:,} more rows)")


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", type=click.Choice(["csv", "json"]),
              default="csv", help="Output format")
@click.option("--output", "-o", default=None, help="Output file path (default: auto)")
def export(filepath, fmt, output):
    """💾 Export data to CSV or JSON."""
    path = Path(filepath)

    try:
        if path.suffix == ".hc":
            df = read_hc(filepath)
        elif path.suffix == ".hcc":
            df = read_hcc(filepath)
        else:
            click.echo(f"❌ Unsupported: {path.suffix}")
            return
    except Exception as e:
        click.echo(f"❌ Error reading file: {e}")
        return

    if df.empty:
        click.echo("⚠️  No data found.")
        return

    if output is None:
        output = str(path.with_suffix(f".{fmt}"))

    if fmt == "csv":
        df.to_csv(output, index=False)
    elif fmt == "json":
        df.to_json(output, orient="records", date_format="iso", indent=2)

    click.echo(f"✅ Exported {len(df):,} records to {output}")
    click.echo(f"   Format: {fmt.upper()}")
    click.echo(f"   Period: {df['datetime'].iloc[0]} → {df['datetime'].iloc[-1]}")


@main.command()
@click.argument("symbol_path", type=click.Path(exists=True))
def timeframes(symbol_path):
    """⏱️  List available timeframes for a symbol directory."""
    tfs = scan_timeframes(symbol_path)

    if not tfs:
        click.echo("❌ No data files found.")
        return

    click.echo(f"📊 Available timeframes in: {Path(symbol_path).name}\n")
    for tf in tfs:
        icon = "📦" if tf["type"] == "hcc" else "📊"
        click.echo(f"   {icon} {tf['timeframe']:<15} {_format_size(tf['size']):>10}  ({tf['path']})")


if __name__ == "__main__":
    main()
