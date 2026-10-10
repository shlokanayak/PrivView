# pipeline.py - the Admin upload pipeline.
# It runs in a background thread, and after EVERY step it saves its progress and
# results in the database (datasets.summary). The React page polls that, so the
# live animation always shows what the backend is really doing.
#
#   1 validate file   -> sanitiser.check_file
#   2 sanitise name   -> sanitiser.sanitise_filename (done when the row was created)
#   3 structure       -> sanitiser.read_table / validate_structure
#   4 sanitise content-> sanitiser.sanitise_table      (SANITISATION)
#   5 mask            -> masking.apply_additive_masking (PRIVACY MASKING)
#   6 encrypt         -> crypto_utils.encrypt_bytes     (ENCRYPTION)
#   7 store           -> encrypted bytes saved in PostgreSQL
#
# The raw upload only exists as bytes in memory. It is never written to disk and is
# dropped as soon as it has been parsed.
import json
import threading
import time

from sqlalchemy.orm.attributes import flag_modified

import crypto_utils
import masking
import sanitiser
from models import db, Dataset
from security import log_action

# Small pause per step ONLY so the admin can watch the steps happen on small files.
# Set to 0 if you don't want it. The step results themselves are always real.
STEP_DELAY = 0.7

STEPS = [
    ("validate", "Validate file"),
    ("filename", "Sanitise filename"),
    ("structure", "Validate dataset structure"),
    ("sanitise", "Sanitise content"),
    ("masking", "Apply privacy masking"),
    ("encrypt", "Encrypt dataset"),
    ("store", "Store in PostgreSQL"),
]


def new_summary():
    return {"steps": [{"key": k, "label": label, "status": "pending", "detail": ""}
                      for k, label in STEPS],
            "validation": {"passed": None, "error": None}}


def aad_for(dataset_id):
    """Extra authenticated data: ties the ciphertext to ONE dataset row."""
    return f"privview-dataset-{dataset_id}".encode()


def load_protected_dataset(ds):
    """Decrypt a dataset IN MEMORY and return it as a dict:
         {"columns", "column_types", "rows", "masking": {"method", "offsets"}}
    Nothing is written to disk. Used by the admin preview now and by the Analyst stage later."""
    plaintext = crypto_utils.decrypt_bytes(ds.nonce, ds.encrypted_data, aad_for(ds.id))
    return json.loads(plaintext)


def start_pipeline(app, dataset_id, raw, ext, filename_changed, extra_mask_columns, ip):
    thread = threading.Thread(target=run_pipeline, daemon=True,
                              args=(app, dataset_id, raw, ext, filename_changed,
                                    extra_mask_columns, ip))
    thread.start()


def run_pipeline(app, dataset_id, raw, ext, filename_changed, extra_mask_columns, ip):
    with app.app_context():
        ds = db.session.get(Dataset, dataset_id)
        summary = ds.summary
        user_id, name = ds.uploaded_by, ds.name
        current = None

        def save():
            ds.summary = summary
            flag_modified(ds, "summary")        # tell SQLAlchemy the JSON changed
            db.session.commit()

        def set_step(key, status, detail=""):
            for step in summary["steps"]:
                if step["key"] == key:
                    step["status"], step["detail"] = status, detail
            save()

        def begin(key):
            nonlocal current
            current = key
            set_step(key, "running")

        def finish(key, detail):
            time.sleep(STEP_DELAY)
            set_step(key, "done", detail)

        try:
            # ---- 1. validate the file -------------------------------------------
            begin("validate")
            info = sanitiser.check_file(raw, ext)
            summary["validation"].update(extension=ext, size_bytes=info["size_bytes"])
            finish("validate", f"{ext.upper()} file, {info['size_bytes']:,} bytes - type, size and signature OK")

            # ---- 2. filename (cleaned when the row was created) ------------------
            begin("filename")
            summary["filename"] = {"changed": filename_changed, "stored_as": ds.filename}
            finish("filename", "Unsafe characters removed" if filename_changed
                   else "Filename was already safe")

            # ---- 3. read + structure --------------------------------------------
            begin("structure")
            header, rows = sanitiser.read_table(raw, ext)
            raw = None                                   # raw upload is no longer needed
            columns, rows, shape = sanitiser.validate_structure(header, rows)
            ds.record_count, ds.column_count = shape["records"], shape["columns"]
            summary["records"] = shape["records"]
            summary["validation"]["passed"] = True
            finish("structure", f"{shape['records']} records, {shape['columns']} columns, "
                                f"{shape['empty_rows_removed']} empty rows removed")

            # ---- 4. sanitise content (SANITISATION) -------------------------------
            begin("sanitise")
            columns, rows, counts = sanitiser.sanitise_table(columns, rows)
            summary["sanitisation"] = dict(counts, empty_rows_removed=shape["empty_rows_removed"])
            log_action(user_id, "SANITISATION",
                       f"cells={counts['cells_checked']}, xss_like={counts['xss_cells']}, "
                       f"formula={counts['formula_cells']}, control_chars={counts['control_char_cells']}",
                       dataset_name=name, ip=ip)
            finish("sanitise", f"{counts['xss_cells']} XSS-like and {counts['formula_cells']} "
                               f"formula cells neutralised in {counts['cells_checked']} cells")

            # ---- 5. privacy masking (PRIVACY MASKING) -----------------------------
            begin("masking")
            types = masking.detect_column_types(columns, rows)
            rows = masking.convert_numeric_columns(columns, rows, types)
            identifiers = masking.find_identifier_columns(columns, rows, types)   # before values change
            automatic = masking.find_sensitive_columns(columns, types)
            manual, ignored = masking.check_extra_columns(columns, types, extra_mask_columns)
            mask_columns = [c for c in columns if c in automatic or c in manual]
            offsets = {}
            if mask_columns:
                rows, offsets = masking.apply_additive_masking(columns, rows, mask_columns)
            summary["columns"] = [{"name": c, "type": types[c], "masked": c in offsets}
                                  for c in columns]
            summary["masking"] = {
                "applied": bool(mask_columns),
                "method": "Additive masking: value + one secret offset per column",
                "columns": mask_columns,
                "ignored_requests": ignored,
                "identifier_columns": identifiers,
            }                                            # NOTE: the offsets are NOT in the summary
            finish("masking", f"{len(mask_columns)} sensitive numeric column(s) masked"
                   if mask_columns else "No sensitive numeric columns found - nothing masked")

            # ---- 6. encrypt (ENCRYPTION AT REST) ----------------------------------
            begin("encrypt")
            payload = json.dumps({"columns": columns, "column_types": types, "rows": rows,
                                  "masking": {"method": "additive", "offsets": offsets}})
            nonce, encrypted = crypto_utils.encrypt_bytes(payload.encode("utf-8"), aad_for(ds.id))
            payload = rows = offsets = None              # drop plaintext from memory
            summary["encryption"] = {"algorithm": "AES-256-GCM", "encrypted": True,
                                     "encrypted_size_bytes": len(encrypted)}
            finish("encrypt", f"AES-256-GCM, random nonce, key loaded from .env "
                              f"({len(encrypted):,} bytes)")

            # ---- 7. store ---------------------------------------------------------
            begin("store")
            ds.encrypted_data = encrypted
            ds.nonce = nonce
            ds.status = "protected"
            summary["storage"] = {"stored": True, "raw_file_retained": False}
            finish("store", "Encrypted dataset saved in PostgreSQL; raw file was never saved")

            log_action(user_id, "UPLOAD_SUCCESS",
                       f"{ext.upper()}, {ds.record_count} records, "
                       f"{len(summary['masking']['columns'])} column(s) masked, encrypted AES-256-GCM",
                       dataset_name=name, ip=ip)

        except (sanitiser.ValidationError, crypto_utils.CryptoConfigError) as err:
            fail(ds, summary, current, str(err),
                 isinstance(err, sanitiser.ValidationError), user_id, name, ip, save)
        except Exception as err:
            print("PIPELINE ERROR:", repr(err))
            fail(ds, summary, current, "Unexpected error while processing the file.",
                 False, user_id, name, ip, save)


def fail(ds, summary, current, message, is_validation, user_id, name, ip, save):
    """Mark the dataset as failed. No encrypted data is stored for a failed upload."""
    db.session.rollback()
    for step in summary["steps"]:
        if step["key"] == current:
            step["status"], step["detail"] = "failed", message
    if is_validation:
        summary["validation"]["passed"] = False
        summary["validation"]["error"] = message
    ds.status = "failed"
    save()
    log_action(user_id, "UPLOAD_FAILED", message, dataset_name=name, success=False, ip=ip)
