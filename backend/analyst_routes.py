# analyst_routes.py - every ANALYST-only API route.
# Two checks protect each dataset route:
#   1) @role_required("analyst")            -> only the database role "analyst" gets in
#   2) authorised_dataset()                 -> the admin must have granted THIS dataset to
#                                              THIS analyst (dataset_access table)
# The analysis uses only the stored protected copy (decrypted in memory), and analysis.prepare()
# removes every direct-identifier column first. Analysts get aggregates + the PDF report only.
import re
from datetime import datetime

from flask import Blueprint, Response, g, jsonify, request

import analysis
import report_pdf
from models import db, User, Dataset, DatasetAccess
from pipeline import load_protected_dataset
from security import role_required, log_action

analyst_bp = Blueprint("analyst", __name__)

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


class BadRequest(Exception):
    pass


def iso(moment):
    return moment.isoformat() if moment else None


# ---------- access control ----------

def authorised_dataset(dataset_id):
    """The dataset, but ONLY if it is protected and the admin granted it to this analyst."""
    ds = db.session.get(Dataset, dataset_id)
    access = (DatasetAccess.query.filter_by(dataset_id=dataset_id, user_id=g.user.id).first()
              if ds else None)
    if ds is None or access is None or ds.status != "protected":
        log_action(g.user.id, "ACCESS_DENIED", f"analyst requested dataset {dataset_id} "
                   "without permission", success=False)
        return None
    return ds


def open_dataset(dataset_id):
    """Returns (dataset, prepared_data, error_response). Decrypts in memory only."""
    ds = authorised_dataset(dataset_id)
    if ds is None:
        return None, None, (jsonify(error="Dataset not found or not shared with you."), 404)
    try:
        P = analysis.prepare(load_protected_dataset(ds))
    except Exception:
        return None, None, (jsonify(error="This dataset could not be opened."), 500)
    return ds, P, None


def uploader_name(ds):
    owner = db.session.get(User, ds.uploaded_by)
    return owner.username if owner else "unknown"


def read_params(P):
    """Validate the measure / group / filter values sent by the browser."""
    q = request.args
    measure = q.get("measure") or analysis.default_measure(P)
    if measure is not None and measure not in P["measures"]:
        raise BadRequest("Unknown measure.")
    if "group_by" in q:
        group_by = q.get("group_by") or None
    else:
        group_by = P["group_cols"][0] if P["group_cols"] else None
    if group_by is not None and group_by not in P["group_cols"]:
        raise BadRequest("Unknown group field.")

    filters = {}
    for key in ("date_from", "date_to"):
        if q.get(key):
            if not P["time"] or not DATE_PATTERN.fullmatch(q[key]):
                raise BadRequest("Invalid date filter.")
            try:
                datetime.strptime(q[key], "%Y-%m-%d")
            except ValueError:
                raise BadRequest("Invalid date filter.")
            filters[key] = q[key]
    return {"measure": measure, "group_by": group_by, "filters": filters}


# ---------- routes ----------

@analyst_bp.route("/api/analyst/datasets")
@role_required("analyst")
def list_datasets():
    """Only datasets granted to the logged-in analyst. A deleted dataset is simply gone."""
    rows = (db.session.query(Dataset, User.username)
            .join(DatasetAccess, DatasetAccess.dataset_id == Dataset.id)
            .join(User, Dataset.uploaded_by == User.id)
            .filter(DatasetAccess.user_id == g.user.id, Dataset.status == "protected")
            .order_by(Dataset.created_at.desc()).all())
    result = []
    for ds, uploader in rows:
        masking_info = (ds.summary or {}).get("masking") or {}
        result.append({"id": ds.id, "name": ds.name, "description": ds.description,
                       "filename": ds.filename, "file_type": ds.file_type,
                       "record_count": ds.record_count, "column_count": ds.column_count,
                       "masked_fields": len(masking_info.get("columns", [])),
                       "status": "protected",
                       "encryption": ((ds.summary or {}).get("encryption") or {}).get("algorithm"),
                       "updated_at": iso(ds.created_at), "updated_by": uploader})
    return jsonify(datasets=result)


@analyst_bp.route("/api/analyst/datasets/<int:dataset_id>")
@role_required("analyst")
def dataset_info(dataset_id):
    """Opening the workspace: metadata, protection status and the filter options."""
    ds, P, error = open_dataset(dataset_id)
    if error:
        return error
    log_action(g.user.id, "DATASET_OPENED", "Opened the protected analysis workspace",
               dataset_name=ds.name)
    return jsonify(id=ds.id, name=ds.name, description=ds.description, filename=ds.filename,
                   file_type=ds.file_type, record_count=ds.record_count,
                   column_count=ds.column_count, status=ds.status,
                   updated_at=iso(ds.created_at), updated_by=uploader_name(ds),
                   fields=analysis.field_list(P), options=analysis.options(P),
                   protection=analysis.protection_info(ds.summary or {}, P))


@analyst_bp.route("/api/analyst/datasets/<int:dataset_id>/analysis")
@role_required("analyst")
def dataset_analysis(dataset_id):
    ds, P, error = open_dataset(dataset_id)
    if error:
        return error
    try:
        params = read_params(P)
    except BadRequest as e:
        return jsonify(error=str(e)), 400
    result = analysis.analyse(P, params["filters"], params["measure"], params["group_by"])
    return jsonify(result)


@analyst_bp.route("/api/analyst/datasets/<int:dataset_id>/report.pdf")
@role_required("analyst")
def download_report(dataset_id):
    ds, P, error = open_dataset(dataset_id)
    if error:
        return error
    try:
        params = read_params(P)
    except BadRequest as e:
        return jsonify(error=str(e)), 400
    result = analysis.analyse(P, params["filters"], params["measure"], params["group_by"])
    if result.get("suppressed"):
        return jsonify(error=result["message"]), 400
    info = {"name": ds.name, "filename": ds.filename, "updated_by": uploader_name(ds),
            "updated_at": ds.created_at.astimezone().strftime("%d %b %Y, %H:%M")}
    pdf = report_pdf.build_report(info, analysis.protection_info(ds.summary or {}, P),
                                  result, params, g.user.username)
    log_action(g.user.id, "REPORT_DOWNLOAD", f"PDF report ({params['measure']})",
               dataset_name=ds.name)
    name = ds.filename.rsplit(".", 1)[0] + "_report.pdf"
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "Cache-Control": "no-store"})
