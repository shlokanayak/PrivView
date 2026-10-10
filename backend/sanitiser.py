# sanitiser.py - INPUT VALIDATION + FILE SANITISATION.
# This file does NOT mask or encrypt anything. It only:
#   1. checks that the upload is a real, safe CSV/XLSX file
#   2. cleans the filename
#   3. checks the table structure
#   4. neutralises dangerous cell content (XSS-like HTML/script, formula injection)
import csv
import io
import math
import os
import re
import unicodedata
import zipfile
from datetime import date, datetime
from html import escape

import openpyxl

ALLOWED_EXTENSIONS = ("csv", "xlsx")
MAX_FILE_SIZE = 5 * 1024 * 1024          # 5 MB
MAX_UNZIPPED_SIZE = 50 * 1024 * 1024     # protects against "zip bombs" inside .xlsx
MAX_ROWS = 50000
MAX_COLUMNS = 50
MAX_CELL_LENGTH = 1000


class ValidationError(Exception):
    """The upload is not acceptable. The message is shown to the admin."""


# ------------------------------------------------------------------
# 1. File validation
# ------------------------------------------------------------------
def check_file(raw, ext):
    """Check extension, size and the real file signature (not just the name)."""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Only .csv and .xlsx files are allowed.")
    if len(raw) == 0:
        raise ValidationError("The file is empty.")
    if len(raw) > MAX_FILE_SIZE:
        raise ValidationError(f"The file is larger than {MAX_FILE_SIZE // (1024 * 1024)} MB.")

    if ext == "csv":
        if b"\x00" in raw:                                   # NUL bytes = binary file renamed to .csv
            raise ValidationError("This is not a text CSV file (binary data found).")
        try:
            raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValidationError("The CSV must be saved with UTF-8 encoding.")
    else:
        if raw[:4] != b"PK\x03\x04":                         # every real .xlsx is a zip file
            raise ValidationError("This is not a real .xlsx file (wrong file signature).")
        try:
            archive = zipfile.ZipFile(io.BytesIO(raw))
            names, infos = archive.namelist(), archive.infolist()
        except zipfile.BadZipFile:
            raise ValidationError("The .xlsx file is corrupted.")
        if "xl/workbook.xml" not in names:
            raise ValidationError("This zip file is not an Excel workbook.")
        if any("vbaProject" in n for n in names):            # macros
            raise ValidationError("Workbooks that contain macros are not allowed.")
        if sum(i.file_size for i in infos) > MAX_UNZIPPED_SIZE:
            raise ValidationError("The workbook expands to an unsafe size.")
    return {"size_bytes": len(raw)}


# ------------------------------------------------------------------
# 2. Filename sanitisation
# ------------------------------------------------------------------
def sanitise_filename(filename):
    """Return (safe_name, changed). Removes folders (../), odd characters, long names."""
    original = str(filename)
    name = os.path.basename(original.replace("\\", "/"))              # drop any folder part
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)                      # whitelist characters
    name = re.sub(r"\.{2,}", ".", name).lstrip(".")                   # no "..", no hidden files
    if "." in name:
        base, ext = name.rsplit(".", 1)
        name = base[:80] + "." + ext[:10]
    else:
        name = name[:80]
    if not name:
        name = "dataset"
    return name, name != original


# ------------------------------------------------------------------
# 3. Reading the file + structure validation
# ------------------------------------------------------------------
def cell_to_text(value):
    """Every cell becomes plain text first, so nothing can be 'executed' later."""
    if value is None:
        return ""
    formula_text = getattr(value, "text", None)          # openpyxl array formulas
    if formula_text:
        value = formula_text
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)


def read_table(raw, ext):
    """Return (header_row, data_rows) as lists of text. Formulas are never evaluated."""
    rows = []
    try:
        if ext == "csv":
            text = raw.decode("utf-8-sig")
            first_line = text.split("\n", 1)[0]
            delimiter = max(",;\t", key=first_line.count)       # most frequent separator
            reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
            source = reader
        else:
            workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=False)
            source = workbook.worksheets[0].iter_rows(values_only=True)   # first sheet only

        for row in source:
            rows.append([cell_to_text(c) for c in row])
            if len(rows) > MAX_ROWS + 1000:
                raise ValidationError(f"The file has more than {MAX_ROWS} rows.")
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("The file could not be read. It may be corrupted or not a valid CSV/XLSX.")

    if not rows:
        raise ValidationError("The file has no content.")
    return rows[0], rows[1:]


def validate_structure(header, rows):
    """Check the table shape. Returns (columns, clean_rows, info)."""
    header = list(header)
    while header and header[-1].strip() == "":               # ignore empty columns at the right
        header.pop()
    if len(header) < 2:
        raise ValidationError("The first row must contain at least 2 column names.")
    if len(header) > MAX_COLUMNS:
        raise ValidationError(f"The file has more than {MAX_COLUMNS} columns.")
    for i, name in enumerate(header, start=1):
        if not name.strip():
            raise ValidationError(f"Column {i} has no name.")
    lowered = [h.strip().lower() for h in header]
    if len(set(lowered)) != len(lowered):
        raise ValidationError("Column names must be unique.")

    clean_rows, empty_removed = [], 0
    for line_no, row in enumerate(rows, start=2):
        if any(cell.strip() for cell in row[len(header):]):
            raise ValidationError(f"Row {line_no} has more values than there are column names.")
        row = row[:len(header)] + [""] * (len(header) - len(row))   # pad short rows
        if not any(cell.strip() for cell in row):
            empty_removed += 1
            continue
        clean_rows.append(row)

    if not clean_rows:
        raise ValidationError("The file has column names but no data rows.")
    if len(clean_rows) > MAX_ROWS:
        raise ValidationError(f"The file has more than {MAX_ROWS} rows.")
    return header, clean_rows, {"records": len(clean_rows), "columns": len(header),
                                "empty_rows_removed": empty_removed}


# ------------------------------------------------------------------
# 4. Content sanitisation
# ------------------------------------------------------------------
HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z!?]")                      # <script>, </div>, <img ...
JS_SCHEME = re.compile(r"(javascript|vbscript)\s*:", re.I)         # javascript:alert(1)
HTML_DATA = re.compile(r"data\s*:\s*text/html", re.I)
EVENT_HANDLER = re.compile(
    r"\b(on(?:error|load|click|mouse\w+|focus|blur|submit|change|input|key\w+))\s*=", re.I)


def to_number(text):
    """'12', '-5.5', '1,200.50' -> float.  Anything else -> None."""
    t = text.strip()
    if re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    if re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", t):
        value = float(t)
        if math.isfinite(value):
            return value
    return None


def looks_dangerous_html(text):
    return bool(HTML_TAG.search(text) or JS_SCHEME.search(text)
                or HTML_DATA.search(text) or EVENT_HANDLER.search(text))


def neutralise_html(text):
    """Turn script-like content into harmless plain text."""
    text = escape(text, quote=False)                                # < > & become &lt; &gt; &amp;
    text = JS_SCHEME.sub(lambda m: m.group(1) + "[blocked]:", text)
    text = HTML_DATA.sub("data[blocked]:text/html", text)
    text = EVENT_HANDLER.sub(lambda m: m.group(1) + "[blocked]=", text)
    return text


def sanitise_cell(text, counts):
    """Clean ONE cell and count what was found. `counts` is a dict that is updated."""
    counts["cells_checked"] += 1

    # a) control / invisible characters (hidden text tricks, right-to-left override ...)
    text = re.sub(r"[\t\r\n]+", " ", text)
    cleaned = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf"))
    if cleaned != text:
        counts["control_char_cells"] += 1
    text = cleaned

    # b) very long cells
    if len(text) > MAX_CELL_LENGTH:
        text = text[:MAX_CELL_LENGTH]
        counts["long_cells"] += 1

    # c) XSS-like content: only cells that really contain HTML/script are changed
    if looks_dangerous_html(text):
        text = neutralise_html(text)
        counts["xss_cells"] += 1

    # d) CSV / Excel formula injection: =, +, -, @ at the start.
    #    Real numbers such as -5 or +3.2 are fine. A lone "-" is also fine.
    start = text.lstrip()
    if start[:1] in ("=", "+", "-", "@") and len(start) > 1 and to_number(start) is None:
        text = "'" + text            # the apostrophe makes Excel treat the cell as plain text
        counts["formula_cells"] += 1
    return text


def new_counts():
    return {"cells_checked": 0, "xss_cells": 0, "formula_cells": 0,
            "control_char_cells": 0, "long_cells": 0, "header_cells_changed": 0}


def sanitise_table(columns, rows):
    """Sanitise headers and every data cell. Returns (columns, rows, counts)."""
    counts = new_counts()
    new_columns = []
    for name in columns:
        cleaned = sanitise_cell(name.strip(), counts)
        if cleaned != name.strip():
            counts["header_cells_changed"] += 1
        new_columns.append(cleaned)
    if len({c.lower() for c in new_columns}) != len(new_columns):
        raise ValidationError("Column names are not unique after cleaning.")

    # also remember WHICH records and fields had something neutralised (shown to analysts)
    def changes():
        return (counts["xss_cells"] + counts["formula_cells"]
                + counts["control_char_cells"] + counts["long_cells"])

    rows_hit, columns_hit, new_rows = set(), set(), []
    for r, row in enumerate(rows):
        new_row = []
        for c, cell in enumerate(row):
            before = changes()
            new_row.append(sanitise_cell(cell.strip(), counts))
            if changes() != before:
                rows_hit.add(r)
                columns_hit.add(c)

        new_rows.append(new_row)
    counts["records_affected"] = len(rows_hit)
    counts["fields_affected"] = len(columns_hit)
    counts["affected_field_names"] = [new_columns[c] for c in sorted(columns_hit)]
    return new_columns, new_rows, counts


def clean_text_field(text, max_length):
    """For short form fields (description, column names typed by the admin)."""
    return sanitise_cell(str(text).strip()[:max_length], new_counts())
