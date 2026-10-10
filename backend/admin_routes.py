# admin_routes.py - every ADMIN-ONLY API route.
# Each route has @role_required("admin"), so the Flask backend decides access
# (the database role), never the React page.
import csv
import io
import re
from datetime import timedelta

from flask import Blueprint, Response, current_app, g, jsonify, request

import sanitiser
from models import db, now, User, Dataset, DatasetAccess, ActivityLog, LoginAttempt
from pipeline import new_summary, start_pipeline, load_protected_dataset
from security import role_required, log_action, mask_email

admin_bp = Blueprint("admin", __name__)

NAME_PATTERN = re.compile(r"[A-Za-z0-9 _().,&-]{3,100}")


def iso(moment):
    return moment.isoformat() if moment else None


# ======================= DATASETS =======================

def dataset_to_dict(ds, username, full=False):
    """Never includes the encrypted data or any masking offset."""
    data = {"id": ds.id, "name": ds.name, "filename": ds.filename, "file_type": ds.file_type,
            "status": ds.status, "record_count": ds.record_count,
            "column_count": ds.column_count, "created_at": iso(ds.created_at),
            "uploaded_by": username}
    if full:
        data["description"] = ds.description
        data["summary"] = ds.summary
    return data


def fail_if_stuck(ds):
    """If Flask was restarted while a dataset was processing, don't show 'processing' forever."""
    if ds.status == "processing" and now() - ds.created_at > timedelta(minutes=2):
        ds.status = "failed"
        summary = ds.summary or new_summary()
        for step in summary["steps"]:
            if step["status"] in ("running", "pending"):
                step["status"], step["detail"] = "failed", "Processing was interrupted."
                break
        ds.summary = summary
        db.session.commit()


@admin_bp.route("/api/admin/datasets")
@role_required("admin")
def list_datasets():
    rows = (db.session.query(Dataset, User.username)
            .join(User, Dataset.uploaded_by == User.id)
            .order_by(Dataset.id.desc()).all())
    result = []
    for ds, username in rows:
        fail_if_stuck(ds)
        result.append(dataset_to_dict(ds, username))
    return jsonify(datasets=result)


@admin_bp.route("/api/admin/datasets/<int:dataset_id>")
@role_required("admin")
def dataset_detail(dataset_id):
    ds = db.session.get(Dataset, dataset_id)
    if ds is None:
        return jsonify(error="Dataset not found."), 404
    fail_if_stuck(ds)
    owner = db.session.get(User, ds.uploaded_by)
    return jsonify(dataset_to_dict(ds, owner.username if owner else "?", full=True))


def reject_upload(message):
    log_action(g.user.id, "UPLOAD_FAILED", message, success=False)
    return jsonify(error=message), 400


@admin_bp.route("/api/admin/datasets", methods=["POST"])
@role_required("admin")
def upload_dataset():
    # ---- input validation of the form fields ----
    name = request.form.get("name", "").strip()
    if not NAME_PATTERN.fullmatch(name):
        return reject_upload("Dataset name must be 3-100 characters: letters, numbers, "
                             "spaces and - _ . , ( ) &")
    description = sanitiser.clean_text_field(request.form.get("description", ""), 500)
    file = request.files.get("file")
    if file is None or not file.filename:
        return reject_upload("Please choose a file.")

    clean_name, changed = sanitiser.sanitise_filename(file.filename)
    ext = clean_name.rsplit(".", 1)[-1].lower() if "." in clean_name else ""
    raw = file.read()          # kept in memory only; never saved to disk
    extra_columns = [sanitiser.clean_text_field(c, 60)
                     for c in request.form.get("mask_columns", "").split(",") if c.strip()][:20]

    ds = Dataset(name=name, description=description, filename=clean_name, file_type=ext[:10],
                 uploaded_by=g.user.id, status="processing", summary=new_summary())
    db.session.add(ds)
    db.session.commit()

    # the real work happens in the background; the page polls the dataset for progress
    start_pipeline(current_app._get_current_object(), ds.id, raw, ext, changed,
                   extra_columns, request.remote_addr)
    return jsonify(id=ds.id), 202


@admin_bp.route("/api/admin/datasets/<int:dataset_id>/preview")
@role_required("admin")
def dataset_preview(dataset_id):
    """Decrypts the dataset in memory and returns the first 10 MASKED rows."""
    ds = db.session.get(Dataset, dataset_id)
    if ds is None:
        return jsonify(error="Dataset not found."), 404
    if ds.status != "protected":
        return jsonify(error="This dataset is not ready."), 400
    try:
        data = load_protected_dataset(ds)
    except Exception:
        log_action(g.user.id, "DATASET_PREVIEW", "Decryption failed", dataset_name=ds.name,
                   success=False)
        return jsonify(error="Could not decrypt this dataset (wrong or changed key?)."), 500
    log_action(g.user.id, "DATASET_PREVIEW", "Decrypted in memory; first 10 masked rows shown",
               dataset_name=ds.name)
    return jsonify(columns=data["columns"], column_types=data["column_types"],
                   rows=data["rows"][:10])


@admin_bp.route("/api/admin/datasets/<int:dataset_id>/download")
@role_required("admin")
def dataset_download(dataset_id):
    """The complete processed dataset (sanitised + additively masked) as CSV.
    Decrypted in memory only - nothing is written to disk. Original values never existed here."""
    ds = db.session.get(Dataset, dataset_id)
    if ds is None:
        return jsonify(error="Dataset not found."), 404
    if ds.status != "protected":
        return jsonify(error="This dataset is not ready."), 400
    try:
        data = load_protected_dataset(ds)
    except Exception:
        log_action(g.user.id, "DATASET_DOWNLOAD", "Decryption failed", dataset_name=ds.name,
                   success=False)
        return jsonify(error="Could not decrypt this dataset (wrong or changed key?)."), 500
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(data["columns"])
    for row in data["rows"]:
        writer.writerow(["" if v is None else v for v in row])
    log_action(g.user.id, "DATASET_DOWNLOAD",
               f"Protected dataset downloaded as CSV ({len(data['rows'])} records)",
               dataset_name=ds.name)
    name = ds.filename.rsplit(".", 1)[0] + "_protected.csv"       # stored filename is already sanitised
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"',
                             "Cache-Control": "no-store"})


@admin_bp.route("/api/admin/datasets/<int:dataset_id>", methods=["DELETE"])
@role_required("admin")
def delete_dataset(dataset_id):
    ds = db.session.get(Dataset, dataset_id)
    if ds is None:
        return jsonify(error="Dataset not found."), 404
    if ds.status == "processing":
        return jsonify(error="Wait until processing has finished."), 409
    name = ds.name
    db.session.delete(ds)      # removes the row incl. encrypted data; dataset_access rows cascade
    db.session.commit()
    log_action(g.user.id, "DATASET_DELETED", f"Dataset id {dataset_id} permanently deleted",
               dataset_name=name)
    return jsonify(message=f"Dataset '{name}' deleted.")


# ======================= ANALYST ACCESS TO A DATASET =======================

@admin_bp.route("/api/admin/datasets/<int:dataset_id>/access")
@role_required("admin")
def dataset_access_list(dataset_id):
    """Every analyst, and whether he may analyse this dataset."""
    if db.session.get(Dataset, dataset_id) is None:
        return jsonify(error="Dataset not found."), 404
    granted = {a.user_id for a in DatasetAccess.query.filter_by(dataset_id=dataset_id).all()}
    analysts = User.query.filter_by(role="analyst").order_by(User.username).all()
    return jsonify(analysts=[{"id": u.id, "username": u.username, "is_active": u.is_active,
                              "has_access": u.id in granted} for u in analysts])


@admin_bp.route("/api/admin/datasets/<int:dataset_id>/access/<int:user_id>",
                methods=["PUT", "DELETE"])
@role_required("admin")
def dataset_access_change(dataset_id, user_id):
    """PUT = grant access, DELETE = revoke access (takes effect on the analyst's next request)."""
    ds = db.session.get(Dataset, dataset_id)
    user = db.session.get(User, user_id)
    if ds is None or user is None:
        return jsonify(error="Dataset or user not found."), 404
    if user.role != "analyst":
        return jsonify(error="Dataset access can only be granted to analysts."), 400

    existing = DatasetAccess.query.filter_by(dataset_id=dataset_id, user_id=user_id).first()
    if request.method == "PUT":
        if ds.status != "protected":
            return jsonify(error="Only protected datasets can be shared."), 400
        if existing is None:
            db.session.add(DatasetAccess(dataset_id=dataset_id, user_id=user_id,
                                         granted_by=g.user.id))
            db.session.commit()
            log_action(g.user.id, "DATASET_ACCESS_GRANTED", f"Granted to {user.username}",
                       dataset_name=ds.name)
        return jsonify(message=f"{user.username} can now analyse '{ds.name}'.")

    if existing is not None:
        db.session.delete(existing)
        db.session.commit()
        log_action(g.user.id, "DATASET_ACCESS_REVOKED", f"Revoked from {user.username}",
                   dataset_name=ds.name)
    return jsonify(message=f"{user.username} no longer has access to '{ds.name}'.")


# ======================= USERS =======================

@admin_bp.route("/api/admin/users")
@role_required("admin")
def list_users():
    users = User.query.order_by(User.id).all()
    return jsonify(users=[{"id": u.id, "username": u.username, "email": mask_email(u.email),
                           "role": u.role, "is_active": u.is_active,
                           "created_at": iso(u.created_at), "is_you": u.id == g.user.id}
                          for u in users])


def blocked(message):
    log_action(g.user.id, "USER_UPDATE_BLOCKED", message, success=False)
    return jsonify(error=message), 403


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["PATCH"])
@role_required("admin")
def update_user(user_id):
    target = db.session.get(User, user_id)
    if target is None:
        return jsonify(error="User not found."), 404

    data = request.get_json(silent=True) or {}
    new_role = data.get("role", target.role)
    new_active = data.get("is_active", target.is_active)
    if new_role not in ("admin", "analyst") or not isinstance(new_active, bool):
        return jsonify(error="Invalid role or status."), 400
    if new_role == target.role and new_active == target.is_active:
        return jsonify(message="No change.")

    # rule 1: an admin can never change their own role or status
    if target.id == g.user.id:
        return blocked("You cannot change your own role or status.")

    # rule 2: the last active admin can never be demoted or deactivated
    if target.role == "admin" and target.is_active and (new_role != "admin" or not new_active):
        other_admins = User.query.filter(User.role == "admin", User.is_active.is_(True),
                                         User.id != target.id).count()
        if other_admins == 0:
            return blocked("The last remaining admin cannot be demoted or deactivated.")

    old_role, old_active = target.role, target.is_active
    target.role, target.is_active = new_role, new_active
    if not new_active:     # cancel unfinished OTP logins of a deactivated user
        LoginAttempt.query.filter_by(user_id=target.id, status="pending").update(
            {"status": "replaced"})
    db.session.commit()

    if old_role != new_role:
        log_action(g.user.id, "ROLE_CHANGED", f"{target.username}: {old_role} -> {new_role}")
    if old_active != new_active:
        log_action(g.user.id, "USER_STATUS_CHANGED",
                   f"{target.username}: {'active' if new_active else 'inactive'}")
    return jsonify(message=f"{target.username} updated.")


# ======================= ACTIVITY LOG =======================

@admin_bp.route("/api/admin/logs")
@role_required("admin")
def list_logs():
    rows = (db.session.query(ActivityLog, User.username)
            .outerjoin(User, ActivityLog.user_id == User.id)
            .order_by(ActivityLog.id.desc()).limit(300).all())
    return jsonify(logs=[{"id": log.id, "username": username, "role": log.role,
                          "action": log.action, "dataset_name": log.dataset_name,
                          "details": log.details, "success": log.success,
                          "created_at": iso(log.created_at)}
                         for log, username in rows])
