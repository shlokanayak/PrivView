import re
import secrets

from sanitiser import to_number

FINANCIAL_KEYWORDS = (
    "salary", "income", "wage", "balance", "amount", "loan", "credit", "debit", "payment",
    "revenue", "profit", "tax", "bill", "charge", "premium", "cost", "expense",
)
MEDICAL_KEYWORDS = (
    "glucose", "cholesterol", "systolic", "diastolic", "bloodpressure", "bmi",
    "heartrate", "pulse", "weight", "dosage",
)
SENSITIVE_KEYWORDS = FINANCIAL_KEYWORDS + MEDICAL_KEYWORDS

ID_WORDS = ("id", "no", "number", "num", "code", "key", "index")
NOT_ID_ENDINGS = ("paid", "valid", "void")      

NAME_WORDS = {
    "Email addresses": {"email", "emailid", "mail", "gmail"},
    "Phone numbers": {"phone", "mobile", "mob", "tel", "telephone", "cell", "whatsapp", "contact",
                      "landline", "fax"},
    "Addresses": {"address", "addr", "street", "locality", "landmark", "pincode", "pin", "postcode",
                  "zip", "zipcode"},
    "Government IDs (Aadhaar / PAN / passport)": {"aadhaar", "aadhar", "adhar", "uid", "uidai",
                  "pan", "passport", "voter", "epic", "licence", "license", "dl", "ssn", "gstin"},
    "Date of birth": {"dob", "birth", "birthdate", "birthday", "born"},
    "Names": {"name", "fname", "lname", "firstname", "lastname", "fullname", "surname", "forename",
              "initials", "patient", "customer", "client", "holder", "nominee", "guardian",
              "spouse", "father", "mother", "husband", "wife", "beneficiary", "applicant",
              "borrower", "guarantor", "signatory", "doctor", "physician", "surgeon", "nurse",
              "consultant", "manager", "officer", "agent", "employee", "referred", "referral",
              "assigned", "owner", "representative", "relative"},
    "Other direct identifiers": {"upi", "vpa", "username", "userid", "login", "ip", "imei",
                                 "mac", "vehicle", "registration"},
}

SAFE_WORDS = {"hospital", "branch", "department", "dept", "product", "merchant", "city", "state",
              "company", "bank", "ward", "clinic", "plan", "drug", "medicine", "test", "disease",
              "diagnosis", "procedure", "scheme", "insurer", "insurance", "vendor", "store",
              "region", "zone", "district", "country", "category", "type", "status", "segment",
              "specialty", "speciality", "grade", "class", "level", "group", "role", "designation",
              "mode", "channel", "count", "total", "fee", "fees", "rating", "score", "age",
              "gender", "sex", "tier", "since", "years", "months", "days", "date", "time"}
STRONG_WORDS = {"email", "emailid", "phone", "mobile", "aadhaar", "aadhar", "adhar", "passport",
                "address", "pincode", "dob", "birthdate", "birthday", "ssn", "uidai", "gstin",
                "surname", "firstname", "lastname", "fullname", "username"}   

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
AADHAAR_RE = re.compile(r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?0?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
PASSPORT_RE = re.compile(r"\b[A-PR-WY][1-9]\d{6}\b")
HONORIFIC_RE = re.compile(r"^(?:dr|mr|mrs|ms|miss|shri|smt|sri|prof|er|adv)\b\.?\s+[A-Za-z]")

CONTENT_KINDS = (("Email addresses", EMAIL_RE), ("Government IDs (Aadhaar / PAN / passport)", PAN_RE),
                 ("Government IDs (Aadhaar / PAN / passport)", AADHAAR_RE),
                 ("Government IDs (Aadhaar / PAN / passport)", PASSPORT_RE),
                 ("Phone numbers", PHONE_RE))


def _simple(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def is_identifier_like(name):
    tokens = re.split(r"[^a-z0-9]+", re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).lower())
    tokens = [t for t in tokens if t]
    simple = _simple(name)
    if (tokens and tokens[-1] in ID_WORDS) or simple in ID_WORDS:
        return True
    if simple.endswith(("number", "code")):
        return True
    return simple.endswith("id") and len(simple) > 2 and not simple.endswith(NOT_ID_ENDINGS)


def category_of(name):
    simple = _simple(name)
    if any(word in simple for word in FINANCIAL_KEYWORDS):
        return "Financial"
    if any(word in simple for word in MEDICAL_KEYWORDS):
        return "Medical"
    return "Other sensitive numeric"


def detect_column_types(columns, rows):
    types = {}
    for i, col in enumerate(columns):
        values = [row[i] for row in rows if row[i] != ""]
        numeric = bool(values) and all(to_number(v) is not None for v in values)
        types[col] = "numeric" if numeric else "text"
    return types


def convert_numeric_columns(columns, rows, types):
    new_rows = []
    for row in rows:
        new_row = []
        for col, cell in zip(columns, row):
            if types[col] == "numeric":
                new_row.append(to_number(cell) if cell != "" else None)
            else:
                new_row.append(cell)
        new_rows.append(new_row)
    return new_rows


def find_sensitive_columns(columns, types):
    found = []
    for col in columns:
        name = _simple(col)
        if types[col] != "numeric" or is_identifier_like(col):
            continue
        if any(word in name for word in SENSITIVE_KEYWORDS):
            found.append(col)
    return found


def _words(name):
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    words = [w for w in re.split(r"[^a-z0-9]+", spaced.lower()) if w]
    return set(words) | {_simple(name)}


def _cell_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip().lstrip("'").strip()


def identifier_kinds(columns, rows, types):
    found = {}
    for i, col in enumerate(columns):
        words = _words(col)
        kind = None
        for k, names in NAME_WORDS.items():
            hit = words & names
            if not hit:
                continue
            if (words & SAFE_WORDS) and not (hit & STRONG_WORDS):
                continue
            if k == "Names" and "name" not in hit and is_identifier_like(col):
                continue                     
            kind = k
            break
        
        if kind is None:
            texts = [t for t in (_cell_text(r[i]) for r in rows) if t]
            if types.get(col) == "numeric":
                digits = [t for t in texts if t.isdigit()]
                if texts and len(digits) / len(texts) >= 0.5:
                    if sum(bool(re.fullmatch(r"[6-9]\d{9}", t)) for t in digits) / len(texts) >= 0.5:
                        kind = "Phone numbers"
                    elif sum(bool(re.fullmatch(r"[2-9]\d{11}", t)) for t in digits) / len(texts) >= 0.5:
                        kind = "Government IDs (Aadhaar / PAN / passport)"
            else:
                for label, pattern in CONTENT_KINDS:
                    if any(pattern.search(t) for t in texts):
                        kind = label
                        break
                if kind is None and any(HONORIFIC_RE.match(t, re.I) for t in texts):
                    kind = "Names"
        if kind:
            found[col] = kind
    return found


def find_identifier_columns(columns, rows=None, types=None):
    if rows is None:
        rows, types = [], {}
    return list(identifier_kinds(columns, rows, types))


def check_extra_columns(columns, types, requested):
    lookup = {c.lower(): c for c in columns}
    accepted, ignored = [], []
    for name in requested:
        col = lookup.get(name.strip().lower())
        if col is None:
            ignored.append(f"'{name}' was not found")
        elif types[col] != "numeric":
            ignored.append(f"'{col}' is not numeric")
        else:
            accepted.append(col)
    return accepted, ignored


def _make_offset(values):
    spread = max(values) - min(values)
    if spread == 0:
        spread = abs(values[0]) or 1.0
    factor = 1 + secrets.randbelow(900) / 100         
    sign = 1 if secrets.randbelow(2) else -1
    return round(sign * factor * spread, 2)


def apply_additive_masking(columns, rows, mask_columns):
    offsets = {}
    for col in mask_columns:
        i = columns.index(col)
        values = [row[i] for row in rows if row[i] is not None]
        offsets[col] = _make_offset(values)

    masked_rows = []
    for row in rows:
        row = list(row)
        for col, k in offsets.items():
            i = columns.index(col)
            if row[i] is not None:
                row[i] = round(row[i] + k, 6)
        masked_rows.append(row)
    return masked_rows, offsets


def unmask_stat(stat, value, offset, count=1):
    if stat in ("mean", "min", "max", "median"):
        return value - offset
    if stat == "sum":
        return value - offset * count
    return value                                    
