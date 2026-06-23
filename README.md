# BOM Diff Tool

A Python desktop tool for comparing BOM (Bill of Materials) files and detecting differences.  
Supports lifecycle checking (Obsolete / NRND detection) via the **DigiKey API** and **Mouser API**.

**[日本語版はこちら → README_JP.md](README_JP.md)**

```
┌──────────────────────────────────────────────────────────────┐
│  ⬡  BOM Diff Tool          v2.2  +  DigiKey / Mouser API   │
├───────────────┬──────────────────────────────────────────────┤
│ OLD BOM FILE  │  ┌─ Tabs ──────────────────────────────────┐ │
│ [old.xlsx  ]… │  │ ＋Added │－Removed │△Qty │△Mfr │⚡Life │ │
│               │  ├─────────────────────────────────────────┤ │
│ NEW BOM FILE  │  │ Part Number  │ Mfr Name │ Qty  │  ...   │ │
│ [new.xlsx  ]… │  │ GRM188R61... │ Murata   │ 100  │  ...   │ │
│               │  └─────────────────────────────────────────┘ │
│ ▶ Compare    │                                               │
│ ─────────────│  ⚡ Lifecycle Tab                              │
│ DIGIKEY API  │  ┌─────────────────────────────────────────┐ │
│ Client ID    │  │ Part Number  │ Status    │ ...           │ │
│ [••••••••••] │  │ GRM188R61... │ Obsolete  │ ...           │ │
│ Client Secret│  │ LQW18AN10... │ Active    │ ...           │ │
│ [••••••••••] │  │ RC0402JR-... │ Not Found │ ...           │ │
│⚡ Check DK   │  └─────────────────────────────────────────┘ │
│ ─────────────│  SUBSTITUTES  (DigiKey / Mouser)              │
│ MOUSER API   │  ┌─────────────────────────────────────────┐ │
│ API Key      │  │ Mfr Part No │ DK/Mouser P/N │ Source    │ │
│ [••••••••••] │  └─────────────────────────────────────────┘ │
│⚡ Check MS   │                                               │
│ ─────────────│                                    ⚙ Settings│
│ SUMMARY      │                                               │
│ Added    [ 1]│                                               │
│ Removed  [ 1]│                                               │
│ Qty Δ    [ 1]│                                               │
│ Mfr Δ    [ 1]│                                               │
│ Obsolete [ 2]│                                               │
│ NRND     [ 1]│                                               │
│↓ Save Report │                                               │
└───────────────┴──────────────────────────────────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| BOM diff comparison | Automatically detects added, removed, quantity changes, and manufacturer changes |
| Custom column names | Change column names via ⚙ Settings (saved to config.ini) |
| DigiKey lifecycle check | Color-coded display of Active / NRND / Obsolete status via DigiKey API |
| Mouser lifecycle check | Color-coded display of Active / NRND / Obsolete status via Mouser API |
| Substitute parts display | Shows DigiKey Substitutions / Mouser SuggestedReplacement with source label |
| Excel report output | Exports results to separate sheets in an Excel file |
| Prepare tool | Removes unnecessary columns from any Excel file and saves as old/new.xlsx |
| CLI mode | Run without GUI using the `--cli` option |

---

## Requirements

- Python 3.11 or later
- Windows / macOS / Linux (requires tkinter)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/bom-diff-tool.git
cd bom-diff-tool

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create the config file
cp config.ini.example config.ini
# Open config.ini and set your API credentials
```

---

## Usage

### BOM Comparison Tool (Main)

```bash
python main.py          # GUI mode (default)
python main.py --cli    # CLI mode
```

**GUI workflow:**

1. Select the OLD and NEW Excel files using the **…** buttons (or type the paths directly)
2. Click **▶ Compare** to view the differences
3. Optionally check lifecycle status — enter credentials and click one of:
   - **⚡ Check DigiKey** — uses DigiKey API (Client ID + Client Secret required)
   - **⚡ Check Mouser** — uses Mouser Search API (API Key required)
4. Click **↓ Save Excel Report** to export the results

### Prepare Tool (Preprocessing)

```bash
python prepare.py
```

Removes unnecessary columns from any Excel file and saves it as `old.xlsx` or `new.xlsx`.  
When you change column names via **⚙ Settings**, the 4 configured columns are automatically checked ON.

### CLI Mode

```bash
python main.py --cli --old old.xlsx --new new.xlsx --output report.xlsx
```

---

## Custom Column Names

The default column names are:

| Role | Default |
|---|---|
| Part Number (index key) | `Manufacturer Part Number` |
| Manufacturer | `Manufacturer Name` |
| Quantity | `Requested Quantity 1` |
| Description | `Description` |

**How to change:** Click the ⚙ Settings button in the GUI → enter column names → save.  
Settings are automatically saved to `config.ini` and persist across restarts.

> **Note:** Column names must match the actual header names in your Excel files exactly.  
> Use the **Prepare tool** to keep only the 4 required columns before running the comparison.

---

## DigiKey API Setup

1. Create an account at [DigiKey Developer Portal](https://developer.digikey.com/)
2. Register an application to get a **Client ID** and **Client Secret**
3. Add the credentials to `config.ini` or use environment variables

```ini
[digikey]
client_id     = YOUR_CLIENT_ID_HERE
client_secret = YOUR_CLIENT_SECRET_HERE
```

**Using environment variables (recommended):**

```bash
# Windows
set DIGIKEY_CLIENT_ID=your_client_id
set DIGIKEY_CLIENT_SECRET=your_client_secret

# Mac / Linux
export DIGIKEY_CLIENT_ID=your_client_id
export DIGIKEY_CLIENT_SECRET=your_client_secret
```

---

## Mouser API Setup

1. Create an account at [Mouser API Hub](https://www.mouser.com/api-hub/)
2. Generate an **API Key** from the developer portal
3. Add the key to `config.ini` or use an environment variable

```ini
[mouser]
api_key = YOUR_MOUSER_API_KEY_HERE
```

**Using an environment variable (recommended):**

```bash
# Windows
set MOUSER_API_KEY=your_api_key

# Mac / Linux
export MOUSER_API_KEY=your_api_key
```

> **Rate limit:** 30 requests/minute, 1,000 requests/day.

---

## Lifecycle Status Colors

| Color | Status | Meaning |
|---|---|---|
| 🔴 Red | Obsolete | Part has been discontinued |
| 🟠 Orange | NRND | Not Recommended for New Designs |
| 🟢 Green | Active | Currently available |
| ⬛ Gray | Not Found | Part not found in the API database |

---

## Sample Data

`sample_old.xlsx` and `sample_new.xlsx` contain dummy data for testing.

Select them via the **…** buttons in the GUI, or copy them first:

```bash
# macOS / Linux
cp sample_old.xlsx old.xlsx
cp sample_new.xlsx new.xlsx

# Windows
copy sample_old.xlsx old.xlsx
copy sample_new.xlsx new.xlsx
```

Then run `python main.py` and click **▶ Compare**.

The sample data includes the following changes between old and new:

| Change type | Part |
|---|---|
| Added | ERJ-1GEJ5R1C |
| Added | RC0402JR-070R1L |
| Removed | MMBT3904LT1G |
| Quantity changed | LQW18AN10NG00D (50 → 80) |
| Manufacturer changed | ERJ-2RKF1001X (Panasonic → Yageo) |

---

## Project Structure

```
bom-diff-tool/
├── main.py                  # Entry point (BOM comparison tool)
├── prepare.py               # Preprocessing tool
├── requirements.txt         # Python dependencies
├── config.ini.example       # Config file template (no credentials)
├── sample_old.xlsx          # Sample data (old BOM)
├── sample_new.xlsx          # Sample data (new BOM)
├── README.md                # This file (English)
├── README_JP.md             # Japanese README
├── LICENSE                  # MIT License
├── CHANGELOG.md             # Version history
├── src/
│   ├── column_config.py     # Column name settings (read/write)
│   ├── comparator.py        # BOM comparison logic
│   ├── digikey_client.py    # DigiKey API client
│   ├── mouser_client.py     # Mouser API client
│   ├── gui.py               # Main GUI
│   ├── loader.py            # Excel loader
│   ├── preprocessor.py      # Preprocessing logic
│   ├── report.py            # Excel report output
│   └── settings_dialog.py   # Column name settings dialog
├── tests/
│   └── test_all.py          # Automated tests (pytest)
└── .github/
    └── workflows/
        └── test.yml         # GitHub Actions CI
```

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## License

[MIT License](LICENSE)
