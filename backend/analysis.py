import math
import re
import statistics
from collections import defaultdict
from datetime import datetime

import masking

MIN_GROUP_SIZE = 3
MAX_GROUPS = 12
MAX_TREND_POINTS = 36

DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y",
                "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y", "%Y-%m"]

GRAIN_KEYS = {
    "day": lambda d: d.strftime("%Y-%m-%d"),
    "month": lambda d: d.strftime("%Y-%m"),
    "quarter": lambda d: f"{d.year}-Q{(d.month - 1) // 3 + 1}",
    "year": lambda d: str(d.year),
}

def num(value):
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"

def detect_date_format(values):
    values = [v for v in values if v]
    if len(values) < 3:
        return None
    best, best_count = None, 0
    for fmt in DATE_FORMATS:
        count = 0
        for v in values:
            try:
                datetime.strptime(v, fmt)
                count += 1
            except ValueError:
                pass
        if count > best_count:
            best, best_count = fmt, count
    return best if best_count / len(values) >= 0.9 else None


def find_time_axis(P):
    for col in P["columns"]:
        if P["types"][col] != "text":
            continue
        i = P["index"][col]
        fmt = detect_date_format([r[i] for r in P["rows"][:300]])
        if fmt:
            dates = []
            for r in P["rows"]:
                try:
                    dates.append(datetime.strptime(r[i], fmt))
                except ValueError:
                    dates.append(None)
            return {"column": col, "dates": dates, "grains": ["day", "month", "quarter", "year"]}
    for col in P["columns"]:
        if P["types"][col] == "numeric" and "year" in col.lower() and col not in P["masked"]:
            i = P["index"][col]
            values = [r[i] for r in P["rows"]]
            if all(v is None or (float(v).is_integer() and 1900 <= v <= 2100) for v in values):
                dates = [datetime(int(v), 1, 1) if v is not None else None for v in values]
                return {"column": col, "dates": dates, "grains": ["year"]}
    return None


RECORD_ID_UNIQUE = 0.9     

def withheld_columns(columns, rows, types):
    withheld = masking.identifier_kinds(columns, rows, types)
    for i, col in enumerate(columns):
        if col in withheld or not masking.is_identifier_like(col):
            continue
        values = [r[i] for r in rows if r[i] not in ("", None)]
        if len(values) >= 5 and len(set(values)) / len(values) >= RECORD_ID_UNIQUE:
            withheld[col] = "Record IDs"
    return withheld


def prepare(payload):
    columns, types, rows = payload["columns"], payload["column_types"], payload["rows"]
    withheld = withheld_columns(columns, rows, types)
    keep = [i for i, c in enumerate(columns) if c not in withheld]
    columns = [columns[i] for i in keep]
    rows = [[r[i] for i in keep] for r in rows]
    types = {c: types[c] for c in columns}
    kinds = defaultdict(int)
    for kind in withheld.values():
        kinds[kind] += 1              
    P = {
        "columns": columns, "types": types, "rows": rows,
        "index": {c: i for i, c in enumerate(columns)},
        "masked": set(payload["masking"]["offsets"].keys()) & set(columns),
        "withheld": [{"kind": k, "count": n} for k, n in sorted(kinds.items())],
    }
    P["time"] = find_time_axis(P)
    time_col = P["time"]["column"] if P["time"] else None

    P["measures"] = [c for c in columns if types[c] == "numeric"
                     and not masking.is_identifier_like(c) and c != time_col]

    P["group_cols"] = []
    for c in columns:
        if types[c] != "text" or c == time_col:
            continue
        values = [r[P["index"][c]] for r in rows if r[P["index"][c]] != ""]
        distinct = len(set(values))
        if 2 <= distinct <= MAX_GROUPS and len(values) / distinct >= 2:  
            P["group_cols"].append(c)
    return P


def default_measure(P):
    for c in P["measures"]:
        if c in P["masked"]:
            return c
    return P["measures"][0] if P["measures"] else None


def field_list(P):
    fields = []
    for c in P["columns"]:
        if P["time"] and c == P["time"]["column"]:
            role = "date"
        elif c in P["measures"]:
            role = "measure"
        elif c in P["group_cols"]:
            role = "category"
        else:
            role = "other"
        fields.append({"name": c, "type": P["types"][c], "masked": c in P["masked"], "role": role})
    return fields


def options(P):
    groups = [{"name": c} for c in P["group_cols"]]
    time = None
    if P["time"]:
        dates = [d for d in P["time"]["dates"] if d]
        time = {"column": P["time"]["column"], "min": min(dates).date().isoformat(),
                "max": max(dates).date().isoformat()}
    return {"measures": [{"name": c, "masked": c in P["masked"]} for c in P["measures"]],
            "default_measure": default_measure(P),
            "group_columns": groups,
            "default_group": P["group_cols"][0] if P["group_cols"] else None,
            "time": time}


def protection_info(summary, P):
    san = summary.get("sanitisation") or {}
    masked_cols = [c for c in P["columns"] if c in P["masked"]]
    mask_idx = [P["index"][c] for c in masked_cols]
    masked_records = sum(1 for r in P["rows"] if any(r[i] is not None for i in mask_idx))
    categories = defaultdict(list)
    for c in masked_cols:
        categories[masking.category_of(c)].append(c)
    return {
        "sanitisation": {
            "status": "Completed" if san else "Unknown",
            "cells_checked": san.get("cells_checked"),
            "xss_cells": san.get("xss_cells"),
            "formula_cells": san.get("formula_cells"),
            "control_char_cells": san.get("control_char_cells"),
            "records_affected": san.get("records_affected"),   
            "fields_affected": san.get("fields_affected"),
            "affected_field_names": san.get("affected_field_names"),
        },
        "masking": {
            "status": "Applied" if masked_cols else "Not needed",
            "method": "Additive masking (each protected value is shifted by a secret constant)",
            "records_affected": masked_records,
            "fields_affected": len(masked_cols),
            "columns": masked_cols,
        },
        "categories": [{"category": k, "columns": v} for k, v in categories.items()],
        "withheld": P["withheld"],       
        "encryption": (summary.get("encryption") or {}).get("algorithm", "AES-256-GCM"),
        "raw_file_retained": (summary.get("storage") or {}).get("raw_file_retained", False),
    }

def select_rows(P, f):
    d_from = datetime.strptime(f["date_from"], "%Y-%m-%d") if f.get("date_from") else None
    d_to = datetime.strptime(f["date_to"], "%Y-%m-%d") if f.get("date_to") else None
    selected = []
    for n, row in enumerate(P["rows"]):
        if d_from or d_to:
            d = P["time"]["dates"][n] if P["time"] else None
            if d is None or (d_from and d < d_from) or (d_to and d.date() > d_to.date()):
                continue
        selected.append(n)
    return selected

def describe(values):
    n = len(values)
    q1, q3 = (statistics.quantiles(values, n=4, method="inclusive")[0::2]
              if n >= 2 else (values[0], values[0]))
    return {"n": n, "mean": round(statistics.mean(values), 4),
            "median": round(statistics.median(values), 4),
            "std": round(statistics.stdev(values), 4) if n >= 2 else 0.0,
            "min": round(min(values), 4), "max": round(max(values), 4),
            "q1": round(q1, 4), "q3": round(q3, 4)}


def trend_for(P, idx, measure, overall_std):
    mi = P["index"][measure]
    rows = P["rows"]
    t = P["time"]
    points, grain, hidden, source = [], None, 0, None

    if t:
        pairs = [(t["dates"][n], rows[n][mi]) for n in idx
                 if t["dates"][n] is not None and rows[n][mi] is not None]
        chosen = None
        for g in t["grains"]:                    
            buckets = defaultdict(list)
            for d, v in pairs:
                buckets[GRAIN_KEYS[g](d)].append(v)
            valid = {k: v for k, v in buckets.items() if len(v) >= MIN_GROUP_SIZE}
            if len(buckets) <= MAX_TREND_POINTS and len(valid) >= 3:
                chosen = (g, buckets, valid)
                break
            if len(valid) >= 2:                 
                chosen = chosen if chosen and chosen[0] != "fallback" else ("fallback", g, buckets, valid)
        if chosen and chosen[0] == "fallback":
            chosen = (chosen[1], chosen[2], chosen[3])
        if chosen:
            grain, buckets, valid = chosen
            points = [{"label": k, "mean": round(statistics.mean(v), 4), "count": len(v)}
                      for k, v in sorted(valid.items())]
            hidden = len(buckets) - len(valid)
            source = t["column"]

    if not points:                              
        vals = [rows[n][mi] for n in idx if rows[n][mi] is not None]
        chunks = min(10, len(vals) // MIN_GROUP_SIZE)
        if chunks >= 3:
            size = len(vals) / chunks
            for c in range(chunks):
                lo, hi = round(c * size), round((c + 1) * size)
                part = vals[lo:hi]
                points.append({"label": f"{lo + 1}-{hi}", "mean": round(statistics.mean(part), 4),
                               "count": len(part)})
            grain, source = "sequence", None

    if len(points) < 2:
        return {"available": False,
                "reason": "Not enough records per period to show a trend (each point needs at least 3)."}

    first, last = points[0]["mean"], points[-1]["mean"]
    change = last - first
    if overall_std == 0 or abs(change) < 0.1 * overall_std:
        direction = "flat"
    else:
        direction = "rising" if change > 0 else "falling"
    masked = measure in P["masked"]
    return {"available": True, "grain": grain, "source_column": source, "points": points,
            "hidden_periods": hidden, "change": round(change, 4), "direction": direction,
            "change_pct": None if masked or first == 0 else round(change / abs(first) * 100, 1)}


def groups_for(P, idx, measure, group_col):
    gi, mi = P["index"][group_col], P["index"][measure]
    buckets = defaultdict(list)
    for n in idx:
        v, g = P["rows"][n][mi], P["rows"][n][gi]
        if v is not None and g != "":
            buckets[g].append(v)
    visible = {g: v for g, v in buckets.items() if len(v) >= MIN_GROUP_SIZE}
    hidden = len(buckets) - len(visible)
    if len(visible) < 2:
        return {"available": False, "group_column": group_col, "hidden_groups": hidden,
                "reason": "Need at least 2 groups with 3 or more records each."}
    all_values = [v for vs in visible.values() for v in vs]
    overall = statistics.mean(all_values)
    rows = [{"group": g, "count": len(vs), "mean": round(statistics.mean(vs), 4),
             "median": round(statistics.median(vs), 4),
             "std": round(statistics.stdev(vs), 4),
             "diff_from_overall": round(statistics.mean(vs) - overall, 4)}
            for g, vs in visible.items()]
    rows.sort(key=lambda r: r["diff_from_overall"], reverse=True)
    return {"available": True, "group_column": group_col, "overall_mean": round(overall, 4),
            "groups": rows, "hidden_groups": hidden}


def distribution_for(values):
    n, lo, hi = len(values), min(values), max(values)
    if lo == hi:
        return [{"label": num(lo), "from": lo, "to": hi, "count": n}]
    bins = min(10, max(4, round(1 + 3.3 * math.log10(n))))
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        counts[min(int((v - lo) / width), bins - 1)] += 1
    return [{"label": f"{num(lo + k * width)} to {num(lo + (k + 1) * width)}",
             "from": round(lo + k * width, 4), "to": round(lo + (k + 1) * width, 4),
             "count": counts[k]} for k in range(bins)]


def correlations_for(P, idx, measure):
    mi = P["index"][measure]
    out = []
    for c in P["measures"]:
        if c == measure:
            continue
        ci = P["index"][c]
        pairs = [(P["rows"][n][mi], P["rows"][n][ci]) for n in idx
                 if P["rows"][n][mi] is not None and P["rows"][n][ci] is not None]
        if len(pairs) < MIN_GROUP_SIZE:
            continue
        xs, ys = zip(*pairs)
        try:
            r = statistics.correlation(xs, ys)
        except statistics.StatisticsError:     
            continue
        out.append({"column": c, "masked": c in P["masked"], "r": round(r, 3), "n": len(pairs)})
    out.sort(key=lambda d: abs(d["r"]), reverse=True)
    return out[:8]


def analyse(P, f, measure, group_by):
    total = len(P["rows"])
    idx = select_rows(P, f)
    base = {"records_total": total, "records_selected": len(idx), "min_group_size": MIN_GROUP_SIZE}

    if len(idx) < MIN_GROUP_SIZE:
        return dict(base, suppressed=True,
                    message=f"Fewer than {MIN_GROUP_SIZE} records match these filters, so the results "
                            "are hidden to protect privacy. Widen the filters.")
    if measure is None:
        return dict(base, suppressed=False, no_measures=True,
                    message="This dataset has no numeric fields that can be analysed.")

    mi = P["index"][measure]
    values = [P["rows"][n][mi] for n in idx if P["rows"][n][mi] is not None]
    if len(values) < MIN_GROUP_SIZE:
        return dict(base, suppressed=True,
                    message=f"Fewer than {MIN_GROUP_SIZE} records have a value for '{measure}'.")

    stats = describe(values)
    summary_stats = []
    for c in P["measures"]:
        ci = P["index"][c]
        vals = [P["rows"][n][ci] for n in idx if P["rows"][n][ci] is not None]
        if len(vals) >= MIN_GROUP_SIZE:
            summary_stats.append(dict(describe(vals), column=c, masked=c in P["masked"],
                                      missing=len(idx) - len(vals)))

    coverage = None
    if P["time"]:
        dates = [P["time"]["dates"][n] for n in idx if P["time"]["dates"][n] is not None]
        if dates:
            coverage = {"column": P["time"]["column"], "from": min(dates).date().isoformat(),
                        "to": max(dates).date().isoformat()}

    return dict(base, suppressed=False, no_measures=False,
                measure={"name": measure, "masked": measure in P["masked"]},
                stats=stats,
                trend=trend_for(P, idx, measure, stats["std"]),
                groups=groups_for(P, idx, measure, group_by) if group_by else None,
                distribution=distribution_for(values),
                correlations=correlations_for(P, idx, measure),
                summary_stats=summary_stats, coverage=coverage,
                masked_fields=len(P["masked"]))
