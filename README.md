# 🔍 HCC Reader — MetaTrader 5 History File Parser

[![PyPI](https://img.shields.io/pypi/v/hcc-reader?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/hcc-reader/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://python.org)
[![Downloads](https://img.shields.io/pypi/dm/hcc-reader?color=green)](https://pypi.org/project/hcc-reader/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey?logo=windows)](https://www.microsoft.com/windows)

> **Đọc trực tiếp file lịch sử MT5 (.hcc/.hc) bằng Python — không cần mở MT5 terminal.**

## 🎯 Vấn đề cần giải quyết

MetaTrader 5 lưu dữ liệu lịch sử giá (*historical data*) vào 2 loại file binary **proprietary** (không công khai format):

| File | Tên gọi | Nội dung | Vị trí |
|------|---------|----------|--------|
| `.hcc` | History Compressed | M1 candles gốc, nén theo năm | `history/<symbol>/<year>.hcc` |
| `.hc` | History Cache | Timeframe đã tính sẵn | `history/<symbol>/cache/<TF>.hc` |

**Vấn đề:** Muốn đọc data này bằng Python, cách thông thường là phải cài MetaTrader5 package + mở terminal + đăng nhập tài khoản. Không thể đọc offline, không thể chạy trên server, không thể batch-process.

**Giải pháp:** Reverse-engineer format binary → đọc trực tiếp bằng pure Python.

## 🧠 Quá trình tư duy & Reverse Engineering

### Bước 1: Khảo sát file binary

```
Hex dump file .hc (Daily cache):
0000: f6 01 00 00 43 00 6f 00 70 00 79 00 72 00 69 00  |....C.o.p.y.r.i.|
0010: 67 00 68 00 74 00 20 00 32 00 30 00 30 00 30 00  |g.h.t. .2.0.0.0.|
...
0084: 48 00 69 00 73 00 74 00 6f 00 72 00 79 00 43 00  |H.i.s.t.o.r.y.C.|
```

Phát hiện: Header chứa copyright string dạng **UTF-16LE**, magic number `0x1F6 = 502` (header size).

### Bước 2: Tìm pattern dữ liệu

Sử dụng brute-force search cho float64 trong phạm vi giá hợp lý:

```python
# Tìm giá vàng (2000-3500 USD) trong binary data
for i in range(len(data) - 8):
    val = struct.unpack_from('<d', data, i)[0]
    if 2000.0 < val < 3500.0:
        # Kiểm tra xem có cluster OHLC liên tiếp không
```

Kết quả: Tìm được OHLC cluster tại offset 0x16F4 → Open=2064.59, High=2063.61...

### Bước 3: Xác định cấu trúc

**File .hc — Columnar Format:**
```
[Header 502 bytes]
[Timestamp Index: N × int64]      ← Mảng timestamps liên tiếp
[Count uint32]
[Open Column: N × float64]        ← Tất cả giá Open
[High Column: N × float64]        ← Tất cả giá High
[Low Column: N × float64]
[Close Column: N × float64]
[Volume columns...]
```

**File .hcc — Row-based M1 Records:**
```
[Header 502 bytes]
[Block Index]
[M1 Records: 60 bytes each]
  ├── int64  timestamp
  ├── float64 open, high, low, close
  ├── int64  tick_volume
  ├── int32  spread
  └── int32  real_volume
```

### So sánh với code cũ trên GitHub

| | [solidbullet/mt5](https://github.com/solidbullet/mt5) | [EA31337/CSVtoHCC](https://github.com/EA31337/CSVtoHCC) | **HCC Reader** |
|---|---|---|---|
| Ngôn ngữ | C | C++ | Python 🐍 |
| Format version | Cũ (header 189B, magic 0x81) | Cũ | **Mới (header 502B, magic 0x1F6)** |
| Đọc .hc cache | ❌ | ❌ | ✅ |
| Đọc .hcc | ✅ (format cũ) | ✅ (format cũ) | ✅ (format mới 2024+) |
| CLI tool | ❌ | ❌ | ✅ |
| Export CSV/JSON | Hạn chế | ❌ | ✅ |
| Auto-scan terminal | ❌ | ❌ | ✅ |
| pandas DataFrame | ❌ | ❌ | ✅ |

## 🚀 Cài đặt

```bash
pip install hcc-reader
```

Hoặc cài từ source:

```bash
git clone https://github.com/hungpixi/hcc-reader.git
cd hcc-reader
pip install -e .
```

## 📖 Sử dụng

### Python API

```python
from hcc_reader import read_hc, read_hcc

# Đọc file cache (.hc) - Daily, H1, M5...
df = read_hc("path/to/XAUUSDm/cache/Daily.hc")
print(df.head())
#                   datetime     open     high      low    close  tick_volume  spread  real_volume
# 0  2024-01-01 00:00:00+00:00  2064.59  2063.61  2059.58  2042.93       29792      17           0
# 1  2024-01-02 00:00:00+00:00  2062.64  2078.77  2058.06  2078.39       ...        ...          ...

# Đọc file M1 (.hcc) - dữ liệu 1 phút
df_m1 = read_hcc("path/to/USOILm/2024.hcc")
print(f"Records: {len(df_m1):,}")
```

### CLI

```bash
# Scan tất cả MT5 terminal trên máy
hcc-reader scan

# Xem thông tin file
hcc-reader info "path/to/Daily.hc"

# Đọc và hiển thị data
hcc-reader read "path/to/Daily.hc" --rows 10

# Export ra CSV
hcc-reader export "path/to/Daily.hc" -f csv -o output.csv

# Export ra JSON
hcc-reader export "path/to/2024.hcc" -f json

# Liệt kê timeframes có sẵn
hcc-reader timeframes "path/to/XAUUSDm/"
```

### Ví dụ thực tế: Phân tích XAUUSD

```python
from hcc_reader import read_hc, scan_terminals

# Tự động tìm MT5 terminal
terminals = scan_terminals()
print(f"Found {len(terminals)} MT5 terminal(s)")

# Đọc Daily data
df = read_hc(r"C:\Users\...\history\XAUUSDm\cache\Daily.hc")

# Tính SMA 20
df['sma20'] = df['close'].rolling(20).mean()

# Lọc ngày giá tăng
bullish = df[df['close'] > df['open']]
print(f"Bullish days: {len(bullish)}/{len(df)} ({len(bullish)/len(df)*100:.1f}%)")
```

## 📁 Cấu trúc dự án

```
hcc-reader/
├── hcc_reader/
│   ├── __init__.py      # Package exports
│   ├── hc_parser.py     # .hc cache file parser (columnar format)
│   ├── hcc_parser.py    # .hcc compressed file parser (M1 records)
│   ├── scanner.py       # Auto-detect MT5 terminals
│   └── cli.py           # Command-line interface
├── pyproject.toml       # PyPI package config
├── LICENSE
└── README.md
```

## ⚙️ Hỗ trợ

| Tính năng | Trạng thái |
|-----------|------------|
| `.hc` cache files (Daily, H1, M5...) | ✅ Hoạt động |
| `.hcc` M1 compressed files | ✅ Hoạt động |
| Export CSV | ✅ |
| Export JSON | ✅ |
| pandas DataFrame | ✅ |
| Auto-scan MT5 terminals | ✅ |
| CLI tool | ✅ |
| Windows support | ✅ |

## 🛣️ Hướng phát triển

- [ ] **Resample**: Tự tính timeframe từ M1 data (M5, H1, Daily...) không cần cache
- [ ] **Merge years**: Nối nhiều file `.hcc` thành dataset liên tục  
- [ ] **Streaming**: Đọc file lớn (20MB+) không cần load toàn bộ vào RAM
- [ ] **MT4 support**: Đọc file `.hst` (format cũ hơn)
- [ ] **Web UI**: Dashboard xem data trực tiếp trên trình duyệt

## 📚 Tham khảo & Nguồn gốc

Format HCC được reverse-engineer dựa trên:
- [solidbullet/mt5](https://github.com/solidbullet/mt5) — C code reverse-engineer format cũ
- [EA31337/CSVtoHCC](https://github.com/EA31337/CSVtoHCC) — CSV ↔ HCC converter (C++)
- [MQL5 Forum discussions](https://www.mql5.com/en/forum) — Community insights về binary structure
- Phân tích binary trực tiếp bằng hex dump + pattern matching

---

## 💼 Bạn muốn tool tương tự?

Bạn đang cần tool **đọc dữ liệu tài chính**, **tự động hóa trading**, hay **xây hệ thống phân tích kỹ thuật**?

| Bạn cần | Chúng tôi đã làm ✅ |
|---------|---------------------|
| Đọc data MT5 offline | HCC Reader (repo này) |
| Bot trade tự động | EA MQL5 + Python signal |
| Dashboard phân tích | Trading Signal Dashboard |
| Scraping dữ liệu | Browser Automation + AI Agent |
| Hệ thống Marketing AI | Comarai AI Agency |

<p align="center">

**🚀 [Yêu cầu Demo](https://comarai.com)** · **💬 [Zalo](https://zalo.me/0834422439)** · **📧 [Email](mailto:hungphamphunguyen@gmail.com)**

</p>

---

<p align="center">
<strong>Comarai — Companion for Marketing & AI Automation</strong><br>
<em>4 nhân viên AI làm việc 24/7: Em Sale · Em Content · Em Marketing · Em Trade</em><br><br>
<em>"Tôi không thuê thêm người — tôi thuê AI. Kết quả: chạy 24/7, không nghỉ phép, không drama."</em><br>
— <a href="https://github.com/hungpixi">hungpixi</a>
</p>

<p align="center">
<a href="https://comarai.com">🌐 comarai.com</a> · <a href="https://github.com/hungpixi">GitHub</a> · <a href="https://zalo.me/0834422439">Zalo</a> · <a href="mailto:hungphamphunguyen@gmail.com">Email</a>
</p>
