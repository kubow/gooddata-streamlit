from pathlib import Path

import altair as alt
import requests
import streamlit as st
import streamlit.components.v1 as components
from pandas import DataFrame, Timestamp, to_datetime

from common import LoadGoodDataSdk
# from component import mycomponent # React specific component not relevant here
from helpers import csv_to_ldm_request, html_cytoscape, time_it


def st_folder_selector(st_placeholder, path='.', label='Please, select a folder...'):
    # get base path (directory)
    base_path = '.' if path is None or path == '' else path
    base_path = Path(str(path)).resolve()
    base_path = base_path if base_path.is_dir() else base_path.parent

    # list files in base path directory
    files = [p.name for p in base_path.iterdir()]
    if base_path != '.':
        files.insert(0, '..')
    files.insert(0, '.')

    selected_file = st_placeholder.selectbox(label=label, options=files, key=str(base_path))
    selected_path = base_path / selected_file

    if selected_file == '.':
        return selected_path
    if selected_path.is_dir():
        selected_path = st_folder_selector(st_placeholder=st_placeholder,
                                           path=selected_path, label=label)

    return str(selected_path)


def safe_rows(objs):
    rows = []
    for o in objs or []:
        row = {
            "id": getattr(o, "id", None) or getattr(getattr(o, "identifier", None), "id", None),
            "title": getattr(o, "title", None) or getattr(o, "name", None),
            "tags": None,
        }
        content = getattr(o, "content", None)
        if isinstance(content, dict):
            tags = content.get("tags")
            if row["title"] is None:
                row["title"] = content.get("title") or content.get("name")
        else:
            tags = getattr(o, "tags", None)
            if row["title"] is None:
                row["title"] = getattr(o, "title", None) or getattr(o, "name", None)
        row["tags"] = tags
        rows.append(row)
    return rows

def get_analytics_lists(analytics_obj):
    """Return (metrics, visualizations, dashboards) supporting multiple attribute names."""
    if not analytics_obj:
        return [], [], []
    # metrics can be under metrics or measures
    mx = getattr(analytics_obj, "metrics", None)
    if mx is None:
        mx = getattr(analytics_obj, "measures", [])
    # visualizations may be visualization_objects or visualizations or insights
    vz = getattr(analytics_obj, "visualization_objects", None)
    if vz is None:
        vz = getattr(analytics_obj, "visualizations", None)
    if vz is None:
        vz = getattr(analytics_obj, "insights", [])
    # dashboards may be analytical_dashboards or dashboards
    db = getattr(analytics_obj, "analytical_dashboards", None)
    if db is None:
        db = getattr(analytics_obj, "dashboards", [])
    return list(mx or []), list(vz or []), list(db or [])

def build_dashboard_rows(dashboards, ws_id: str, fc_map: dict | None = None) -> list[dict]:
    base_host = st.secrets.get("GOODDATA_HOST", "").rstrip("/")
    token = st.secrets.get("GOODDATA_TOKEN", "")
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/json"} if token else None
    rows = []
    for d in dashboards or []:
        # base fields
        row = {
            "id": getattr(d, "id", None),
            "title": getattr(d, "title", None),
            "description": getattr(d, "description", None),
            "is_hidden": None,
            "is_valid": None,
            "created_at": getattr(d, "created_at", None) or getattr(d, "created", None),
            "modified_at": getattr(d, "updated_at", None) or getattr(d, "updated", None),
            "filter_context_id": None,
            "filter_context_definition": None,
            # enriched FC fields (computed best-effort)
            "filter_count": None,
            "attribute_filter_count": None,
            "date_filter_count": None,
            "tags": getattr(d, "tags", None),
        }
        content = getattr(d, "content", None)
        if isinstance(content, dict):
            row["description"] = row["description"] or content.get("description")
            # GoodData analytical dashboard often has filterContext or filterContextRef
            fc = content.get("filterContext") or content.get("filterContextRef") or content.get("filter_context")
            if isinstance(fc, dict):
                # try common shapes for id
                row["filter_context_id"] = (
                        fc.get("id")
                        or (fc.get("identifier") or {}).get("id")
                        or (fc.get("ref") or {}).get("id")
                )
                # if definition is embedded, keep it
                if fc.get("filters") or isinstance(fc.get("definition"), dict) or isinstance(fc.get("content"), dict):
                    row["filter_context_definition"] = (
                        fc.get("definition")
                        or fc.get("content")
                        or {"filters": fc.get("filters")}
                    )
            # visibility/validity flags if present
            row["is_hidden"] = content.get("isHidden", row["is_hidden"])
            row["is_valid"] = content.get("isValid", row["is_valid"])
            # prefer tags from content if present
            row["tags"] = content.get("tags", row["tags"])
        # Inject definition from provided map (no REST)
        if (row["filter_context_definition"] is None) and row["filter_context_id"] and isinstance(fc_map, dict):
            try:
                row["filter_context_definition"] = fc_map.get(str(row["filter_context_id"]))
            except Exception:
                pass

        # Compute best-effort counts from the resolved definition (if any)
        try:
            fc_def = row.get("filter_context_definition")
            filt_list = []
            if isinstance(fc_def, dict):
                if isinstance(fc_def.get("filters"), list):
                    filt_list = fc_def.get("filters")
                elif isinstance(fc_def.get("filterContext"), dict) and isinstance(fc_def.get("filterContext").get("filters"), list):
                    filt_list = fc_def.get("filterContext").get("filters")
            row["filter_count"] = len(filt_list) if isinstance(filt_list, list) else row.get("filter_count")
            # attribute/date breakdown if possible
            if isinstance(filt_list, list) and filt_list:
                a_cnt = 0; d_cnt = 0
                for f in filt_list:
                    if not isinstance(f, dict):
                        continue
                    if f.get("attributeFilter") or f.get("attribute_filter"):
                        a_cnt += 1
                    elif f.get("dateFilter") or f.get("date_filter"):
                        d_cnt += 1
                row["attribute_filter_count"] = a_cnt
                row["date_filter_count"] = d_cnt
        except Exception:
            pass

        # Construct links
        if base_host and row["id"]:
            # Two known variants depending on deployment
            embed_url_v1 = f"{base_host}/dashboards/embedded/#/workspace/{ws_id}/dashboard/{row['id']}?showNavigation=false&setHeight=700"
            embed_url_v2 = f"{base_host}/embedded/dashboards/#/workspace/{ws_id}/dashboard/{row['id']}?showNavigation=false&setHeight=700"
            app_url = f"{base_host}/dashboards/#/workspace/{ws_id}/dashboard/{row['id']}"
            row["embed_url"] = embed_url_v1
            row["embed_url_alt"] = embed_url_v2
            row["app_url"] = app_url

        rows.append(row)
    return rows

def build_metric_rows(metrics: list) -> list[dict]:
    """Build enriched rows for metrics including description, MAQL, format, and timestamps.
    Accepts SDK metric objects or dict-like items.
    """
    rows: list[dict] = []
    for m in metrics or []:
        # Base fields
        row = {
            "id": getattr(m, "id", None) or getattr(getattr(m, "identifier", None), "id", None),
            "title": getattr(m, "title", None) or getattr(m, "name", None),
            "description": getattr(m, "description", None),
            "maql": None,
            "format": None,
            "created_at": getattr(m, "created_at", None) or getattr(m, "created", None),
            "modified_at": getattr(m, "updated_at", None) or getattr(m, "updated", None),
            "tags": None,
        }
        content = getattr(m, "content", None)
        if isinstance(content, dict):
            row["description"] = row["description"] or content.get("description")
            # MAQL might be under 'maql' or nested under 'metric'
            row["maql"] = content.get("maql") or (content.get("metric", {}) if isinstance(content.get("metric"), dict) else {}).get("maql")
            # Format may be 'format' or 'content'->'format'
            row["format"] = content.get("format")
            # Prefer tags from content
            row["tags"] = content.get("tags")
            # Timestamps sometimes live in attributes
            attrs = content.get("attributes") if isinstance(content.get("attributes"), dict) else None
            if attrs:
                row["created_at"] = row["created_at"] or attrs.get("created", attrs.get("created_at"))
                row["modified_at"] = row["modified_at"] or attrs.get("updated", attrs.get("updated_at"))
        else:
            # Fallback to direct attributes on the object
            row["maql"] = getattr(m, "maql", None)
            row["format"] = getattr(m, "format", None)
            row["tags"] = getattr(m, "tags", None)
        # Final fallback: if title missing, look into dict conversion
        if row["title"] is None:
            try:
                as_dict = m.to_dict() if hasattr(m, "to_dict") else getattr(m, "__dict__", {})
                if isinstance(as_dict, dict):
                    row["title"] = row["title"] or as_dict.get("title") or as_dict.get("name")
                    c = as_dict.get("content")
                    if isinstance(c, dict):
                        row["maql"] = row["maql"] or c.get("maql")
                        row["format"] = row["format"] or c.get("format")
                        row["description"] = row["description"] or c.get("description")
                        row["tags"] = row["tags"] or c.get("tags")
            except Exception:
                pass
        rows.append(row)
    return rows

def build_visual_rows(visuals: list) -> list[dict]:
    """Build enriched rows for visualizations/insights with description, timestamps, type, and tags.
    Accepts SDK insight objects or dict-like items.
    """
    rows: list[dict] = []
    for v in visuals or []:
        row = {
            "id": getattr(v, "id", None) or getattr(getattr(v, "identifier", None), "id", None),
            "title": getattr(v, "title", None) or getattr(v, "name", None),
            "description": getattr(v, "description", None),
            "type": None,
            "created_at": getattr(v, "created_at", None) or getattr(v, "created", None),
            "modified_at": getattr(v, "updated_at", None) or getattr(v, "updated", None),
            "tags": None,
            "bucket_count": None,
            "measures_count": None,
            "attributes_count": None,
            "has_filters": None,
            "sorts_count": None,
            "measures": None,
            "attributes": None,
        }
        content = getattr(v, "content", None)
        if isinstance(content, dict):
            row["description"] = row["description"] or content.get("description")
            row["tags"] = content.get("tags", row["tags"])
            # common locations for type
            row["type"] = content.get("type") or content.get("visualizationUrl") or content.get("visualization_url")
            # timestamps sometimes live nested
            attrs = content.get("attributes") if isinstance(content.get("attributes"), dict) else None
            if attrs:
                row["created_at"] = row["created_at"] or attrs.get("created", attrs.get("created_at"))
                row["modified_at"] = row["modified_at"] or attrs.get("updated", attrs.get("updated_at"))
            # buckets/filters/sorts summaries (GoodData insight content)
            buckets = content.get("buckets") if isinstance(content.get("buckets"), list) else []
            row["bucket_count"] = len(buckets) if buckets else 0
            measures, attributes = [], []
            try:
                for b in buckets or []:
                    items = b.get("items", []) if isinstance(b, dict) else []
                    for it in items:
                        local_id = it.get("localIdentifier") or it.get("local_identifier")
                        # two common item types: measure/attribute with nested measure/attribute ref
                        m = (it.get("measure") or {}) if isinstance(it.get("measure"), dict) else None
                        a = (it.get("attribute") or {}) if isinstance(it.get("attribute"), dict) else None
                        if m:
                            mid = (m.get("definition") or {}).get("measureDefinition", {}).get("item", {}).get("identifier")
                            measures.append(mid or local_id)
                        if a:
                            aid = (a.get("displayForm") or {}).get("identifier") or (a.get("display_form") or {}).get("identifier")
                            attributes.append(aid or local_id)
            except Exception:
                pass
            row["measures_count"] = len([x for x in measures if x]) if buckets else 0
            row["attributes_count"] = len([x for x in attributes if x]) if buckets else 0
            row["measures"] = ", ".join([str(x) for x in measures if x]) if measures else None
            row["attributes"] = ", ".join([str(x) for x in attributes if x]) if attributes else None
            # filters and sorts
            flt = content.get("filters") if isinstance(content.get("filters"), list) else []
            srt = content.get("sorts") if isinstance(content.get("sorts"), list) else []
            row["has_filters"] = bool(flt)
            row["sorts_count"] = len(srt) if srt else 0
        else:
            row["tags"] = getattr(v, "tags", None)
        if row["title"] is None:
            try:
                as_dict = v.to_dict() if hasattr(v, "to_dict") else getattr(v, "__dict__", {})
                if isinstance(as_dict, dict):
                    row["title"] = row["title"] or as_dict.get("title") or as_dict.get("name")
                    c = as_dict.get("content")
                    if isinstance(c, dict):
                        row["description"] = row["description"] or c.get("description")
                        row["tags"] = row["tags"] or c.get("tags")
                        row["type"] = row["type"] or c.get("type") or c.get("visualizationUrl") or c.get("visualization_url")
            except Exception:
                pass
        rows.append(row)
    return rows

def build_filter_context_rows(ws_id: str, dashes_df: DataFrame | None = None) -> list[dict]:
    """Fetch filter contexts from REST and build enriched rows.
    Includes id, title, description, tags, created/modified timestamps, filter count, and usage by dashboards.
    """
    host = str(st.secrets.get("GOODDATA_HOST", "")).rstrip("/")
    token = st.secrets.get("GOODDATA_TOKEN", "")
    if not host or not token:
        return []
    rows: list[dict] = []
    try:
        url = f"{host}/api/v1/entities/workspaces/{ws_id}/filterContexts?size=200"
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=30)
        if resp.status_code == 200:
            data = resp.json() or {}
            items = data.get("data") or []
            # Precompute dashboard usage
            used_counts = {}
            if isinstance(dashes_df, DataFrame) and not dashes_df.empty and "filter_context_id" in dashes_df.columns:
                try:
                    for v, cnt in dashes_df["filter_context_id"].value_counts().items():
                        used_counts[str(v)] = int(cnt)
                except Exception:
                    used_counts = {}
            for it in items:
                if not isinstance(it, dict):
                    continue
                att = it.get("attributes", {}) if isinstance(it.get("attributes"), dict) else {}
                fid = it.get("id") or (it.get("identifier") or {}).get("id")
                title = att.get("title") or att.get("name")
                desc = att.get("description")
                tags = att.get("tags")
                created = att.get("createdAt") or att.get("created_at") or att.get("created")
                updated = att.get("modifiedAt") or att.get("updated_at") or att.get("updated")
                definition = att.get("content") or att.get("definition") or {}
                filters = definition.get("filters") if isinstance(definition.get("filters"), list) else []
                rows.append({
                    "id": fid,
                    "title": title,
                    "description": desc,
                    "tags": tags,
                    "created_at": created,
                    "modified_at": updated,
                    "filter_count": len(filters) if filters else 0,
                    "definition": definition,
                    "dashboards_using": used_counts.get(str(fid), 0),
                })
    except Exception:
        return rows
    return rows

def build_flat_rows(objs: list) -> list[dict]:
    """Flatten each object's structure (including nested 'content') into a single-level dict."""
    rows = []
    for o in objs or []:
        base = _to_plain_dict(o) or {}
        # Some SDK objects keep payload under 'content'
        if isinstance(base.get("content"), dict):
            flat = _flatten_dict(base)
        else:
            flat = _flatten_dict(base)
        rows.append(flat)
    return rows


def _to_plain_dict(obj) -> dict | None:
    """Best-effort conversion of an SDK object to a plain dict."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        try:
            return obj.to_dict()
        except Exception:
            pass
    try:
        return dict(getattr(obj, "__dict__", {}))
    except Exception:
        return None


def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """Recursively flattens a dict. Lists become indexed with [i] in the path."""
    items = {}
    if not isinstance(d, dict):
        return {parent_key or "value": d}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else str(k)
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key, sep))
        elif isinstance(v, list):
            for i, el in enumerate(v):
                if isinstance(el, (dict, list)):
                    items.update(_flatten_dict(el if isinstance(el, dict) else {"_list": el}, f"{new_key}[{i}]", sep))
                else:
                    items[f"{new_key}[{i}]"] = el
        else:
            items[new_key] = v
    return items


def build_filter_context_rows_from_analytics(analytics_obj, dashes_df: DataFrame | None = None) -> tuple[list[dict], dict]:
    """Extract filter contexts directly from the analytics object.
    Returns a tuple: (rows, fc_map) where fc_map maps filter context id -> definition dict.
    """
    rows: list[dict] = []
    fc_map: dict = {}
    # Dashboard usage counts if provided
    used_counts = {}
    if isinstance(dashes_df, DataFrame) and not dashes_df.empty and "filter_context_id" in dashes_df.columns:
        try:
            for v, cnt in dashes_df["filter_context_id"].value_counts().items():
                used_counts[str(v)] = int(cnt)
        except Exception:
            used_counts = {}
    # Try to read filter contexts from analytics as dict
    try:
        a_dict = _to_plain_dict(analytics_obj) or {}
        fcs = (
            a_dict.get("filter_contexts")
            or a_dict.get("filterContexts")
            or []
        )
        for it in fcs or []:
            # Support both dict items or SDK model dicts
            if isinstance(it, dict):
                fid = it.get("id") or (it.get("identifier") or {}).get("id")
                att = it.get("attributes") if isinstance(it.get("attributes"), dict) else {}
                title = att.get("title") or att.get("name")
                desc = att.get("description")
                tags = att.get("tags")
                created = att.get("createdAt") or att.get("created_at") or att.get("created")
                updated = att.get("modifiedAt") or att.get("updated_at") or att.get("updated")
                # try multiple places for the definition
                definition = (
                    att.get("content") if isinstance(att.get("content"), dict) else None
                ) or (
                    it.get("content") if isinstance(it.get("content"), dict) else None
                ) or (
                    att.get("definition") if isinstance(att.get("definition"), dict) else None
                ) or {}
                # if filters are stored directly on attributes, coerce
                if not definition and isinstance(att.get("filters"), list):
                    definition = {"filters": att.get("filters")}
                if fid:
                    fc_map[str(fid)] = definition
                    # compute counts from definition (various shapes)
                    filt_list = []
                    if isinstance(definition, dict):
                        if isinstance(definition.get("filters"), list):
                            filt_list = definition.get("filters")
                        elif isinstance(definition.get("filterContext"), dict) and isinstance(definition.get("filterContext").get("filters"), list):
                            filt_list = definition.get("filterContext").get("filters")
                    rows.append({
                        "id": fid,
                        "title": title,
                        "description": desc,
                        "tags": tags,
                        "created_at": created,
                        "modified_at": updated,
                        "filter_count": len(filt_list) if isinstance(filt_list, list) else 0,
                        "definition": definition,
                        "dashboards_using": used_counts.get(str(fid), 0),
                    })
    except Exception:
        pass
    # If nothing extracted, try to derive minimal rows from dashboards
    if not rows and isinstance(dashes_df, DataFrame) and not dashes_df.empty and "filter_context_id" in dashes_df.columns:
        try:
            fcs = dashes_df[["filter_context_id", "title"]].dropna().copy()
            fcs = fcs.groupby("filter_context_id").first().reset_index()
            for _, r in fcs.iterrows():
                fid = str(r.get("filter_context_id"))
                rows.append({
                    "id": fid,
                    "title": r.get("title"),
                    "description": None,
                    "tags": None,
                    "created_at": None,
                    "modified_at": None,
                    "filter_count": None,
                    "definition": None,
                    "dashboards_using": used_counts.get(fid, 0),
                })
        except Exception:
            pass
    return rows, fc_map


def main():
    # session variables
    if "analytics" not in st.session_state:
        st.session_state["analytics"] = []
    if "gd" not in st.session_state:
        st.session_state["gd"] = LoadGoodDataSdk(st.secrets["GOODDATA_HOST"], st.secrets["GOODDATA_TOKEN"])
    if "timing" not in st.session_state:
        st.session_state["timing"] = []
    # Unified per-workspace cache
    if "ws_cache" not in st.session_state:
        st.session_state["ws_cache"] = {}
    if "current_ws_id" not in st.session_state:
        st.session_state["current_ws_id"] = None

    st.set_page_config(
        layout="wide", page_icon="favicon.ico", page_title="Streamlit-GoodData integration demo"
    )
    org = st.session_state["gd"].organization()

    with st.sidebar:
        # Details first
        with st.expander("Details", expanded=True):
            st.write("Hostname:", org.attributes.hostname)
            st.write("Organization id:", org.id)
            st.text(st.session_state["gd"].tree())
            st.write(st.session_state["gd"].identity_provider())

        # Then the workspace selector and actions
        ws_name = st.selectbox("Select a workspace", options=[w.name for w in st.session_state["gd"].workspaces])
        refresh_ws = st.button("Reload workspace details")
        # Resolve workspace id
        ws_obj = st.session_state["gd"].specific(ws_name, of_type="workspace", by="name")
        ws_id = ws_obj.id
        # Ensure cache is populated on selection change or explicit reload
        ws_cache = st.session_state.get("ws_cache", {})
        need_load = refresh_ws or (st.session_state.get("current_ws_id") != ws_id) or (ws_id not in ws_cache)
        if need_load:
            with st.spinner("Loading workspace metadata..."):
                # Analytics via SDK wrapper
                try:
                    analytics = st.session_state["gd"].details(wks_id=ws_id, by="id")
                except Exception:
                    analytics = None
                    st.warning("Failed to fetch analytics for the selected workspace.")
                # If analytics object exists but has no expected lists, retry by name
                try:
                    empty_analytics = (
                        analytics is None or (
                            len(getattr(analytics, "metrics", []) or []) == 0 and
                            len(getattr(analytics, "visualization_objects", []) or []) == 0 and
                            len(getattr(analytics, "analytical_dashboards", []) or []) == 0
                        )
                    )
                except Exception:
                    empty_analytics = True
                if empty_analytics:
                    try:
                        analytics = st.session_state["gd"].details(wks_id=ws_name, by="name")
                    except Exception:
                        pass
                # LDM: SDK-first, REST fallback
                datasets_rows, columns_rows, refs_rows = [], [], []
                try:
                    ldm = st.session_state["gd"]._sdk.catalog_workspace_content.get_declarative_ldm(ws_id)
                    ds_list = getattr(getattr(ldm, "ldm", None), "datasets", []) or []
                    for ds in ds_list:
                        ds_id = getattr(ds, "id", None)
                        ds_title = getattr(ds, "title", None) or getattr(ds, "name", None)
                        # Heuristic dataset type detection
                        try:
                            _attrs = getattr(ds, "attributes", []) or []
                            ds_is_date = any(
                                (getattr(a, "granularity", None) or (getattr(getattr(a, "to_dict", None), "__call__", None)() or {}).get("granularity"))
                                for a in _attrs
                            )
                        except Exception:
                            ds_is_date = False
                        datasets_rows.append({
                            "dataset_id": ds_id,
                            "dataset_title": ds_title,
                            "description": getattr(ds, "description", None),
                            "tags": getattr(ds, "tags", None),
                            "dataset_type": "date" if ds_is_date else "regular",
                        })
                        for attr in getattr(ds, "attributes", []) or []:
                            cdict = getattr(attr, "to_dict", None)
                            as_dict = cdict() if callable(cdict) else getattr(attr, "__dict__", {})
                            src_col_val = as_dict.get("source_column") if isinstance(as_dict, dict) else None
                            src_table = None
                            if isinstance(src_col_val, dict):
                                src_table = src_col_val.get("table") or src_col_val.get("name") or src_col_val.get("dataset")
                            columns_rows.append({
                                "dataset_id": ds_id,
                                "dataset_title": ds_title,
                                "column_id": getattr(attr, "id", None),
                                "column_title": getattr(attr, "title", None),
                                "column_description": getattr(attr, "description", None),
                                "tags": getattr(attr, "tags", None),
                                "data_type": as_dict.get("data_type") if isinstance(as_dict, dict) else None,
                                "source_column": (as_dict.get("source_column") if isinstance(as_dict, dict) else None),
                                "source_table": src_table,
                                "column_type": "attribute",
                                "granularity": as_dict.get("granularity") if isinstance(as_dict, dict) else None,
                                "label": as_dict.get("label") if isinstance(as_dict, dict) else None,
                                "is_anchor": as_dict.get("is_anchor") if isinstance(as_dict, dict) else getattr(attr, "is_anchor", None),
                                "default_label": as_dict.get("default_label") if isinstance(as_dict, dict) else getattr(attr, "default_label", None),
                                "sort_label": as_dict.get("sort_label") if isinstance(as_dict, dict) else getattr(attr, "sort_label", None),
                                "labels": as_dict.get("labels") if isinstance(as_dict, dict) else None,
                            })
                        for fact in getattr(ds, "facts", []) or []:
                            cdict = getattr(fact, "to_dict", None)
                            as_dict = cdict() if callable(cdict) else getattr(fact, "__dict__", {})
                            src_col_val = as_dict.get("source_column") if isinstance(as_dict, dict) else None
                            src_table = None
                            if isinstance(src_col_val, dict):
                                src_table = (src_col_val.get("table") or src_col_val.get("name") or src_col_val.get("dataset"))
                            columns_rows.append({
                                "dataset_id": ds_id,
                                "dataset_title": ds_title,
                                "column_id": getattr(fact, "id", None),
                                "column_title": getattr(fact, "title", None),
                                "column_description": getattr(fact, "description", None),
                                "tags": getattr(fact, "tags", None),
                                "data_type": as_dict.get("data_type") if isinstance(as_dict, dict) else None,
                                "source_column": (as_dict.get("source_column") if isinstance(as_dict, dict) else None),
                                "source_table": src_table,
                                "column_type": "fact",
                                "granularity": None,
                                "label": None,
                                "aggregation": as_dict.get("aggregation") if isinstance(as_dict, dict) else getattr(fact, "aggregation", None),
                            })
                        # references (best-effort)
                        try:
                            ds_dict = getattr(ds, "to_dict", lambda: {})()
                            for ref in (ds_dict.get("references") or []):
                                refs_rows.append({
                                    "from_dataset_id": ds_id,
                                    "from_dataset_title": ds_title,
                                    "to_dataset_id": ref.get("dataset") or ref.get("id"),
                                    "columns": ref.get("source_columns") or ref.get("columns"),
                                })
                        except Exception:
                            pass

                except Exception:
                    host = st.secrets.get("GOODDATA_HOST", "").rstrip("/")
                    token = st.secrets.get("GOODDATA_TOKEN", "")
                    if host and token:
                        try:
                            resp = requests.get(
                                f"{host}/api/v1/layout/workspaces/{ws_id}/ldm",
                                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                                timeout=30,
                            )
                            if resp.status_code == 200:
                                data = resp.json() or {}
                                ds_list = (data.get("ldm") or {}).get("datasets", [])
                                for ds in ds_list:
                                    ds_id = ds.get("id")
                                    ds_title = ds.get("title") or ds.get("name")
                                    ds_is_date = any((a or {}).get("granularity") for a in (ds.get("attributes") or []))
                                    datasets_rows.append({
                                        "dataset_id": ds_id,
                                        "dataset_title": ds_title,
                                        "description": ds.get("description"),
                                        "tags": ds.get("tags"),
                                        "dataset_type": "date" if ds_is_date else "regular",
                                    })
                                    for attr in ds.get("attributes", []) or []:
                                        src_col_val = attr.get("source_column")
                                        src_table = None
                                        if isinstance(src_col_val, dict):
                                            src_table = (src_col_val.get("table") or src_col_val.get("name") or src_col_val.get("dataset"))
                                        columns_rows.append({
                                            "dataset_id": ds_id,
                                            "dataset_title": ds_title,
                                            "column_id": attr.get("id"),
                                            "column_title": attr.get("title"),
                                            "column_description": attr.get("description"),
                                            "tags": attr.get("tags"),
                                            "data_type": attr.get("data_type"),
                                            "source_column": attr.get("source_column"),
                                            "source_table": src_table,
                                            "column_type": "attribute",
                                            "granularity": attr.get("granularity"),
                                            "label": attr.get("label"),
                                            "is_anchor": attr.get("is_anchor"),
                                            "default_label": attr.get("default_label"),
                                            "sort_label": attr.get("sort_label"),
                                            "labels": attr.get("labels"),
                                        })
                                    for fact in ds.get("facts", []) or []:
                                        src_col_val = fact.get("source_column")
                                        src_table = None
                                        if isinstance(src_col_val, dict):
                                            src_table = (src_col_val.get("table") or src_col_val.get("name") or src_col_val.get("dataset"))
                                        columns_rows.append({
                                            "dataset_id": ds_id,
                                            "dataset_title": ds_title,
                                            "column_id": fact.get("id"),
                                            "column_title": fact.get("title"),
                                            "column_description": fact.get("description"),
                                            "tags": fact.get("tags"),
                                            "data_type": fact.get("data_type"),
                                            "source_column": fact.get("source_column"),
                                            "source_table": src_table,
                                            "column_type": "fact",
                                            "granularity": None,
                                            "label": None,
                                            "aggregation": fact.get("aggregation"),
                                        })
                                    for ref in ds.get("references", []) or []:
                                        refs_rows.append({
                                            "from_dataset_id": ds_id,
                                            "from_dataset_title": ds_title,
                                            "to_dataset_id": ref.get("dataset") or ref.get("id"),
                                            "columns": ref.get("source_columns") or ref.get("columns"),
                                        })
                        except Exception:
                            pass

                # Ensure workspace-bound data sources are available for mapping and cache
                workspace_datasources: list[dict] = []
                try:
                    ds_list = getattr(st.session_state.get("gd"), "datasources", []) or []
                    for it in ds_list:
                        workspace_datasources.append({
                            "id": getattr(it, "id", None),
                            "name": getattr(it, "name", None) or getattr(it, "title", None) or getattr(it, "id", None),
                        })
                except Exception:
                    workspace_datasources = []
                # Attempt to enrich LDM columns with data source via PDM table mapping (best-effort)
                table_to_ds = {}
                try:
                    # SDK PDM first
                    pdm = st.session_state["gd"]._sdk.catalog_workspace_content.get_declarative_pdm(ws_id)
                    # Try to read tables and their data source ids
                    pdm_dict = getattr(pdm, "to_dict", lambda: {})()
                    # Heuristic traversal
                    tables = []
                    if isinstance(pdm_dict, dict):
                        # Find any list of tables with dataSourceId and name/id
                        def _walk(obj):
                            out = []
                            if isinstance(obj, dict):
                                for k, v in obj.items():
                                    out.extend(_walk(v))
                            elif isinstance(obj, list):
                                for it in obj:
                                    out.extend(_walk(it))
                            else:
                                return []
                            return out
                        # naive extract
                        # fallback to SDK attributes
                        tables = pdm_dict.get("tables") or _walk(pdm_dict)
                    # Build name->ds map
                    if isinstance(tables, list):
                        for t in tables:
                            if isinstance(t, dict):
                                tname = t.get("name") or t.get("id")
                                dsid = t.get("dataSourceId") or t.get("data_source_id")
                                if tname and dsid:
                                    key_full = str(tname).lower()
                                    key_base = key_full.split(".")[-1]
                                    table_to_ds[key_full] = dsid
                                    table_to_ds[key_base] = dsid
                except Exception:
                    # REST fallback
                    host = st.secrets.get("GOODDATA_HOST", "").rstrip("/")
                    token = st.secrets.get("GOODDATA_TOKEN", "")
                    if host and token:
                        try:
                            resp = requests.get(
                                f"{host}/api/v1/layout/workspaces/{ws_id}/pdm",
                                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                                timeout=30,
                            )
                            if resp.status_code == 200:
                                data = resp.json() or {}
                                # Heuristic: expect pdm.tables with name and dataSourceId
                                tables = (data.get("pdm") or {}).get("tables") or []
                                for t in tables:
                                    tname = t.get("name") or t.get("id")
                                    dsid = t.get("dataSourceId") or t.get("data_source_id")
                                    if tname and dsid:
                                        key_full = str(tname).lower()
                                        key_base = key_full.split(".")[-1]
                                        table_to_ds[key_full] = dsid
                                        table_to_ds[key_base] = dsid
                        except Exception:
                            pass

                # If we have any table->DS mapping, annotate columns_rows and datasets_rows summaries
                if table_to_ds and columns_rows:
                    # Pre-build ds id->name map
                    dsid_to_name = {str(d.get("id")): d.get("name") for d in workspace_datasources}
                    for col in columns_rows:
                        # Prefer explicit source_table captured earlier
                        table_name = col.get("source_table")
                        sc = col.get("source_column")
                        # If no explicit table, try parsing from string-valued source_column
                        if not table_name and isinstance(sc, str):
                            s = sc
                            # Common forms: schema.table.column or table.column
                            parts = s.split(".")
                            if len(parts) >= 2:
                                table_name = parts[-2]
                        # If source_column is dict, try its table field
                        if not table_name and isinstance(sc, dict):
                            table_name = sc.get("table") or sc.get("name") or sc.get("dataset")
                        if table_name:
                            key_full = str(table_name).lower()
                            key_base = key_full.split(".")[-1]
                            dsid = table_to_ds.get(key_full) or table_to_ds.get(key_base)
                            if dsid:
                                col["data_source_id"] = dsid
                                col["data_source_name"] = dsid_to_name.get(str(dsid))
                    # Aggregate to dataset level (majority data source among its columns)
                    from collections import Counter
                    ds_majority = {}
                    for ds in datasets_rows:
                        dsid = ds.get("dataset_id")
                        ds_cols = [c for c in columns_rows if c.get("dataset_id") == dsid and c.get("data_source_id")]
                        votes = Counter([c.get("data_source_id") for c in ds_cols])
                        if votes:
                            top_id, _ = votes.most_common(1)[0]
                            ds["data_source_id"] = top_id
                            ds["data_source_name"] = dsid_to_name.get(str(top_id))

                # Build cache entry and set current ws
                ds_df = DataFrame(datasets_rows)
                cols_df = DataFrame(columns_rows)
                refs_df = DataFrame(refs_rows)
                # Prebuild analytics dataframes for render (to avoid recomputation each rerun)
                try:
                    def get_lists(aobj):
                        if not aobj:
                            return [], [], []
                        mx = getattr(aobj, "metrics", None) or getattr(aobj, "measures", [])
                        vz = getattr(aobj, "visualization_objects", None) or getattr(aobj, "visualizations", None) or getattr(aobj, "insights", [])
                        db = getattr(aobj, "analytical_dashboards", None) or getattr(aobj, "dashboards", [])
                        return list(mx or []), list(vz or []), list(db or [])
                    _mx, _vz, _db = get_lists(analytics)
                    pre_metrics_df = DataFrame(build_metric_rows(_mx)) if _mx else DataFrame()
                    pre_visuals_df = DataFrame(build_visual_rows(_vz)) if _vz else DataFrame()
                    pre_filter_ctx_rows, fc_map = build_filter_context_rows_from_analytics(analytics)
                    pre_filter_ctx_df = DataFrame(pre_filter_ctx_rows)
                    pre_dashes_df = DataFrame(build_dashboard_rows(_db, ws_id, fc_map)) if _db else DataFrame()
                except Exception:
                    pre_metrics_df = DataFrame(); pre_visuals_df = DataFrame(); pre_dashes_df = DataFrame(); pre_filter_ctx_df = DataFrame()
                st.session_state.setdefault("ws_cache", {})[ws_id] = {
                    "name": ws_name,
                    "analytics": analytics,
                    "ldm_ds_df": ds_df,
                    "ldm_cols_df": cols_df,
                    "ldm_refs_df": refs_df,
                    "ldm_counts": {"tables": len(ds_df), "columns": len(cols_df)},
                    "datasources": workspace_datasources,
                    "metrics_df": pre_metrics_df,
                    "visuals_df": pre_visuals_df,
                    "dashes_df": pre_dashes_df,
                    "filter_ctx_df": pre_filter_ctx_df,
                }
                st.session_state["current_ws_id"] = ws_id

        # Sidebar cache summary
        ws_cache = st.session_state.get("ws_cache", {})
        cache_entry_sb = ws_cache.get(ws_id, {})
        counts_sb = cache_entry_sb.get("ldm_counts", {"tables": 0, "columns": 0})
        st.caption(f"Cached: {counts_sb.get('tables', 0)} tables • {counts_sb.get('columns', 0)} columns")
        with st.expander("Data actions"):
            current_ws_id = st.session_state.get("current_ws_id")
            cache_entry = ws_cache.get(current_ws_id) or {}
            analytics = cache_entry.get("analytics")

            viz_options = [d.title for d in getattr(analytics, "visualization_objects", [])] if analytics else []
            df_insight = st.selectbox(
                "Select an Insight",
                options=viz_options if viz_options else ["<no insights>"] ,
                disabled=not bool(viz_options),
            )
            # Datasources from SDK wrapper (already available in st.session_state["gd"].datasources)
            try:
                ds_bound = [{"id": getattr(d, "id", None), "name": (getattr(d, "name", None) or getattr(d, "title", None) or getattr(d, "id", None))} for d in (st.session_state.get("gd").datasources or [])]
            except Exception:
                ds_bound = []
            ds_options = [d.get("name") for d in ds_bound] if ds_bound else []
            # Try to derive assigned data source from cached LDM datasets majority mapping
            assigned_ds = None
            try:
                ds_df_cached = cache_entry.get("ldm_ds_df")
                if ds_df_cached is not None and not ds_df_cached.empty and "data_source_id" in ds_df_cached.columns:
                    from collections import Counter
                    votes = Counter([str(x) for x in ds_df_cached["data_source_id"].dropna().astype(str).tolist()])
                    if votes:
                        top_id, _ = votes.most_common(1)[0]
                        name_map = {str(d.get("id")): d.get("name") for d in ds_bound}
                        assigned_ds = {"id": top_id, "name": name_map.get(str(top_id)) or str(top_id)}
            except Exception:
                assigned_ds = None

            if assigned_ds:
                st.selectbox("Assigned data source", [assigned_ds.get("name")], index=0, disabled=True)
                ds_list = assigned_ds.get("name")
                clear_cache = st.button("Clear cache for assigned data source")
            else:
                # Fallback to manual selection if assignment cannot be derived
                ds_list = st.selectbox("Assigned data source", ds_options if ds_options else ["<no datasources>"] , disabled=not bool(ds_options))
                clear_cache = st.button("Clear cache for selected data source", disabled=not bool(ds_options))
            # Enable test only when we have an insight and at least one DS option or an assigned DS
            has_ds_available = bool(assigned_ds) or bool(ds_options)
            run_insight_test = st.button("Test Insight Retrieval", disabled=not (bool(viz_options) and has_ds_available))

            # Persist selections for use outside the sidebar scope
            if run_insight_test:
                st.session_state["_insight_test_request"] = {
                    "insight_title": df_insight,
                    "datasource_name": ds_list,
                    "ws_id": ws_id,
                }
        with st.expander("Data preparation"):
            prep_option = st.radio(
                "1. Choose data preparation method:",
                ("CSV as SQL dataset", "CSV S3 uploader", "LDM preparation")
            )
            uploaded_file = st.file_uploader("2. Upload your CSV file", type=["csv"])
            upload_csv = st.button("3. Process CSV")
        with st.expander("Backup & Restore"):
            st.write("Need to find a way to backup and restore using python sdk")
            backup = st.button("Backup selected workspace")
            # backup_ldm = st.download_button("Backup data model for selected workspace", st.session_state["analytics"])
            # backup_analytics = st.download_button("Backup analytics for selected workspace", st.session_state["analytics"])

    active_ws = st.session_state["gd"].specific(ws_name, of_type="workspace", by="name")
    #if backup_analytics:
    #    st.write(st.session_state["gd"].export(active_ws))
    if backup:
        st.session_state["gd"].export(wks_id=active_ws.id, location=Path.cwd())
        exported_path = Path.cwd().joinpath("gooddata_layouts", org.id, "workspaces", active_ws.id, "analytics_model")
        st.write(f"Workspace: {active_ws.name} backed up to /gooddata_layouts/..., below a list of folders")
        for folder in exported_path.iterdir():
            for file in exported_path.joinpath(folder).glob("*.yaml"):
                st.write(file)
    elif clear_cache:
        ds_active = st.session_state["gd"].get_id(name=ds_list, of_type="datasource")
        st.session_state["gd"].clear_cache(ds_id=ds_active)
        st.write(f"data source {ds_active}: cache cleared!")
    # Inline execution of the Insight Retrieval test
    if st.session_state.get("_insight_test_request"):
        req = st.session_state.pop("_insight_test_request")
        insight_title = req.get("insight_title")
        datasource_name = req.get("datasource_name")
        st.info(f"Testing retrieval of insight '{insight_title}' from data source '{datasource_name}'...")
        t0 = time_it()
        try:
            # Resolve and fetch the insight
            active_ins = st.session_state["gd"].specific(insight_title, of_type="insight", by="name", ws_id=active_ws.id)
            elapsed = time_it(t0, True)
            st.success(f"Insight retrieved in {elapsed:.2f} seconds.")
            # Append timing entry to a session time series for charting
            st.session_state.setdefault("timing", [])
            st.session_state["timing"].append({
                "insight": insight_title,
                "datasource": datasource_name,
                "timestamp": Timestamp.now(),
                "elapsed": elapsed,
            })
            # Time series chart of retrieval times
            if st.session_state["timing"]:
                timing_df = DataFrame(st.session_state["timing"]).copy()
                timing_df["timestamp"] = to_datetime(timing_df["timestamp"])
                timing_df = timing_df.sort_values(["insight", "timestamp"])
                st.caption("Time series of retrieval times for all insights.")
                chart = alt.Chart(timing_df).mark_line(point=True).encode(
                    x=alt.X('timestamp:T', title='Timestamp'),
                    y=alt.Y('elapsed:Q', title='Retrieval time (s)'),
                    color=alt.Color('insight:N', title='Insight'),
                    tooltip=['insight', 'datasource', 'timestamp', 'elapsed']
                ).properties(width='container', height=350)
                st.altair_chart(chart, width='stretch')
                st.dataframe(
                    timing_df[["insight","datasource","timestamp","elapsed"]]
                    .rename(columns={"elapsed":"Retrieval time (s)", "insight": "Insight", "datasource": "Data source", "timestamp": "Timestamp"})
                )
            # Show the dataframe with the insight's content
            st.caption("Insight object data frame (actual data):")
            st.dataframe(active_ins, width='stretch')
        except Exception as e:
            st.error(f"Error retrieving insight: {e}")

    elif upload_csv and uploaded_file is not None:
        if prep_option == "CSV as SQL dataset":
            st.write("Create a new SQL dataset and paste the SQL query (final version should post it directly to the model)")
            with st.form("sql_form"):
                sql_query = st.text_area("SQL Query", height=200)
                submitted = st.form_submit_button("Run SQL")
        elif prep_option == "CSV S3 uploader":
            st.info("[Placeholder] CSV S3 uploader logic will be implemented here.")
        elif prep_option == "LDM preparation":
            st.write("LDM Preparation: Generating request based on CSV fields...")
            st.write(csv_to_ldm_request(uploaded_file))
    else:
        st.write(f"Selected workspace: {active_ws.name}")

        # Read from unified cache
        ws_id_active = st.session_state.get("current_ws_id")
        ws_cache = st.session_state.get("ws_cache", {})
        cache_entry = ws_cache.get(ws_id_active, {})
        analytics = cache_entry.get("analytics")

        # Prefer prebuilt DataFrames from cache; compute only if missing
        metrics_df = cache_entry.get("metrics_df")
        visuals_df = cache_entry.get("visuals_df")
        dashes_df = cache_entry.get("dashes_df")
        if metrics_df is None or visuals_df is None or dashes_df is None:
            mx_list, vz_list, db_list = get_analytics_lists(analytics)
            metrics_df = DataFrame(build_metric_rows(mx_list)) if mx_list else DataFrame()
            visuals_df = DataFrame(build_visual_rows(vz_list)) if vz_list else DataFrame()
            pre_filter_ctx_rows, fc_map = build_filter_context_rows_from_analytics(analytics)
            dashes_df = DataFrame(build_dashboard_rows(db_list, active_ws.id, fc_map)) if db_list else DataFrame()
            # Store back into cache for reuse
            if cache_entry is not None:
                cache_entry["metrics_df"] = metrics_df
                cache_entry["visuals_df"] = visuals_df
                cache_entry["dashes_df"] = dashes_df
                # also (re)build filter contexts
                cache_entry["filter_ctx_df"] = DataFrame(pre_filter_ctx_rows)

        tab_overview, tab_metrics, tab_visuals, tab_dash, tab_filters, tab_ldm, tab_graph = st.tabs([
            "Overview", "Metrics", "Visualizations", "Dashboards", "Filter Contexts", "LDM", "Graph"
        ])

        with tab_overview:
            c1, c2, c3 = st.columns(3)
            c1.metric("Metrics", len(metrics_df))
            c2.metric("Visualizations", len(visuals_df))
            c3.metric("Dashboards", len(dashes_df))
            c4, c5 = st.columns(2)
            ldm_tables = cache_entry.get("ldm_counts", {}).get("tables", 0)
            ldm_cols = cache_entry.get("ldm_counts", {}).get("columns", 0)
            c4.metric("Tables (LDM)", ldm_tables)
            c5.metric("Columns (LDM)", ldm_cols)
            if analytics is None:
                st.info("Workspace analytics not loaded yet. Use 'Reload workspace details' in the sidebar.")
            st.caption("Basic overview of objects in the selected workspace. LDM counts are cached on workspace selection.")

        with tab_metrics:
            st.subheader("Metrics")
            col1, col2, col3 = st.columns([1, 1, 1])
            q_title = col1.text_input("Title contains", key="mx_title_q")
            q_tags = col2.text_input("Tags contains", key="mx_tags_q")
            show_full = col3.checkbox("Show full structure", value=False, key="mx_full")
            df = metrics_df.copy()
            # Ensure enriched columns are present even if cache predates the change
            required_cols = {"description", "maql", "format", "created_at", "modified_at"}
            if not df.empty and not required_cols.issubset(set(df.columns)):
                try:
                    mx_list, _, _ = get_analytics_lists(analytics)
                    df = DataFrame(build_metric_rows(mx_list)) if mx_list else DataFrame()
                    # update cache so subsequent renders use enriched columns
                    cache_entry = st.session_state.get("ws_cache", {}).get(st.session_state.get("current_ws_id"), None)
                    if isinstance(cache_entry, dict):
                        cache_entry["metrics_df"] = df
                except Exception:
                    pass
            # Optional full structure view
            if show_full and analytics is not None:
                try:
                    mx_list, _, _ = get_analytics_lists(analytics)
                    df = DataFrame(build_flat_rows(mx_list)) if mx_list else DataFrame()
                except Exception:
                    pass
            if not df.empty:
                if q_title and "title" in df.columns:
                    df = df[df["title"].astype(str).str.contains(q_title, case=False, na=False)]
                if q_tags and "tags" in df.columns:
                    df = df[df["tags"].astype(str).str.contains(q_tags, case=False, na=False)]
                st.dataframe(df, width='stretch')
            else:
                st.info("No metrics found in this workspace.")

        with tab_visuals:
            st.subheader("Visualizations")
            col1, col2, col3 = st.columns([1, 1, 1])
            q_title = col1.text_input("Title contains", key="viz_title_q")
            q_tags = col2.text_input("Tags contains", key="viz_tags_q")
            show_full = col3.checkbox("Show full structure", value=False, key="vz_full")
            df = visuals_df.copy()
            # Ensure enriched columns are present even if cache predates the change
            required_cols_vz = {"description", "type", "created_at", "modified_at", "bucket_count"}
            if not df.empty and not required_cols_vz.issubset(set(df.columns)):
                try:
                    _, vz_list, _ = get_analytics_lists(analytics)
                    df = DataFrame(build_visual_rows(vz_list)) if vz_list else DataFrame()
                    # update cache so subsequent renders use enriched columns
                    cache_entry = st.session_state.get("ws_cache", {}).get(st.session_state.get("current_ws_id"), None)
                    if isinstance(cache_entry, dict):
                        cache_entry["visuals_df"] = df
                except Exception:
                    pass
            if show_full and analytics is not None:
                try:
                    _, vz_list, _ = get_analytics_lists(analytics)
                    df = DataFrame(build_flat_rows(vz_list)) if vz_list else DataFrame()
                except Exception:
                    pass
            if not df.empty:
                if q_title and "title" in df.columns:
                    df = df[df["title"].astype(str).str.contains(q_title, case=False, na=False)]
                if q_tags and "tags" in df.columns:
                    df = df[df["tags"].astype(str).str.contains(q_tags, case=False, na=False)]
                st.dataframe(df, width='stretch')
            else:
                st.info("No visualizations found in this workspace.")

        with tab_dash:
            st.subheader("Dashboards")
            col1, col2 = st.columns(2)
            q_title = col1.text_input("Title contains", key="dash_title_q")
            q_tags = col2.text_input("Tags contains", key="dash_tags_q")
            df = dashes_df.copy()
            if not df.empty:
                if q_title:
                    df = df[df["title"].astype(str).str.contains(q_title, case=False, na=False)]
                if q_tags and "tags" in df.columns:
                    df = df[df["tags"].astype(str).str.contains(q_tags, case=False, na=False)]
                df = df.fillna("")

                # Render header
                hdr = st.container()
                with hdr:
                    hcols = st.columns([0.5, 0.5, 0.6, 2, 2, 1.2, 0.8, 0.8, 1.2, 1.2, 1.8])
                    hcols[0].markdown("**📎**")
                    hcols[1].markdown("**🌳**")
                    hcols[2].markdown("**🔗**")
                    hcols[3].markdown("**ID**")
                    hcols[4].markdown("**Title**")
                    hcols[5].markdown("**Filter Ctx**")
                    hcols[6].markdown("**Hidden**")
                    hcols[7].markdown("**Valid**")
                    hcols[8].markdown("**Created**")
                    hcols[9].markdown("**Modified**")
                    hcols[10].markdown("**Tags**")

                # Track clicked action
                clicked_action = None
                clicked_dash_id = None
                clicked_dash_title = None

                # Rows
                fc_lookup = {}
                try:
                    fctx_df_cached = cache_entry.get("filter_ctx_df")
                    if isinstance(fctx_df_cached, DataFrame) and not fctx_df_cached.empty:
                        for _, rr in fctx_df_cached.fillna("").iterrows():
                            fc_lookup[str(rr.get("id"))] = rr.to_dict()
                except Exception:
                    fc_lookup = {}

                for _, r in df.iterrows():
                    rid = str(r.get("id", ""))
                    rtitle = str(r.get("title", ""))
                    rfcid = str(r.get("filter_context_id", ""))
                    rhidden = str(r.get("is_hidden", ""))
                    rvalid = str(r.get("is_valid", ""))
                    rcreated = str(r.get("created_at", ""))
                    rmodified = str(r.get("modified_at", ""))
                    rtags = str(r.get("tags", ""))
                    rapp = str(r.get("app_url", ""))
                    fc_display = rfcid or "-"
                    if rfcid and fc_lookup:
                        info = fc_lookup.get(rfcid)
                        if isinstance(info, dict):
                            parts = []
                            t = info.get("title")
                            if t:
                                parts.append(str(t))
                            fc_total = info.get("filter_count")
                            # fallback: try to compute from this row's own definition if missing in cache
                            if (fc_total is None or str(fc_total) == "") and isinstance(r.get("filter_context_definition"), dict):
                                try:
                                    rdef = r.get("filter_context_definition")
                                    if isinstance(rdef.get("filters"), list):
                                        fc_total = len(rdef.get("filters"))
                                    elif isinstance(rdef.get("filterContext"), dict) and isinstance(rdef.get("filterContext").get("filters"), list):
                                        fc_total = len(rdef.get("filterContext").get("filters"))
                                except Exception:
                                    pass
                            if fc_total is not None:
                                parts.append(f"{fc_total} filters")
                            a_cnt = info.get("attribute_filter_count")
                            d_cnt = info.get("date_filter_count")
                            if (a_cnt is not None and str(a_cnt) != "") or (d_cnt is not None and str(d_cnt) != ""):
                                parts.append(f"a:{a_cnt or 0}/d:{d_cnt or 0}")
                            if parts:
                                fc_display = f"{rfcid} • " + " • ".join(parts)
                    cols = st.columns([0.5, 0.5, 0.6, 2, 2, 1.2, 0.8, 0.8, 1.2, 1.2, 1.8])
                    if cols[0].button("📎", key=f"embed_{rid}"):
                        clicked_action, clicked_dash_id, clicked_dash_title = "embed", rid, rtitle
                    if cols[1].button("🌳", key=f"schema_{rid}"):
                        clicked_action, clicked_dash_id, clicked_dash_title = "schema", rid, rtitle
                    if rapp:
                        cols[2].link_button("🔗", rapp)
                    else:
                        cols[2].markdown("-")
                    cols[3].markdown(rid)
                    cols[4].markdown(rtitle or "-")
                    cols[5].markdown(fc_display)
                    cols[6].markdown(rhidden or "-")
                    cols[7].markdown(rvalid or "-")
                    cols[8].markdown(rcreated or "-")
                    cols[9].markdown(rmodified or "-")
                    cols[10].markdown(rtags or "-")

                # Inline render under the table
                if clicked_action == "embed" and clicked_dash_id:
                    t = time_it()
                    try:
                        row_match = dashes_df[dashes_df["id"].astype(str) == str(clicked_dash_id)]
                        embed_url = None
                        embed_url_alt = None
                        if not row_match.empty and "embed_url" in row_match.columns:
                            embed_url = row_match.iloc[0]["embed_url"]
                            embed_url_alt = row_match.iloc[0].get("embed_url_alt")
                        if not embed_url:
                            host = str(st.secrets.get("GOODDATA_HOST", "")).rstrip("/")
                            embed_url = f"{host}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{clicked_dash_id}?showNavigation=false&setHeight=700"
                            embed_url_alt = f"{host}/embedded/dashboards/#/workspace/{active_ws.id}/dashboard/{clicked_dash_id}?showNavigation=false&setHeight=700"
                        # Probe URLs to auto-select a working variant
                        def _is_ok(url: str | None) -> bool:
                            if not url:
                                return False
                            try:
                                r = requests.get(url, timeout=5)
                                return r.status_code < 400
                            except Exception:
                                return False
                        if _is_ok(embed_url):
                            url_to_use = embed_url
                        elif _is_ok(embed_url_alt):
                            url_to_use = embed_url_alt
                        else:
                            # If both probes fail, still try default to allow cookie-auth flows
                            url_to_use = embed_url or embed_url_alt
                        st.caption(f"Embedding: {url_to_use}")
                        components.iframe(url_to_use, 1000, 700)
                        st.write(f"dashboard loaded in {time_it(t, True)*1000} milliseconds")
                    except Exception as _e:
                        st.error(f"Failed to embed dashboard: {_e}")
                elif clicked_action == "schema" and (clicked_dash_title or clicked_dash_id):
                    # Try to render schema by title first; fall back to id
                    try:
                        ident_used = None
                        dashboard_visual = None
                        if clicked_dash_title:
                            ident_used = f"title: {clicked_dash_title}"
                            try:
                                dashboard_visual = st.session_state["gd"].schema(clicked_dash_title, ws_id=active_ws.id)
                            except Exception:
                                dashboard_visual = None
                        if dashboard_visual is None and clicked_dash_id:
                            ident_used = f"id: {clicked_dash_id}"
                            try:
                                dashboard_visual = st.session_state["gd"].schema(clicked_dash_id, ws_id=active_ws.id)
                            except Exception as _e2:
                                st.error(f"Failed to resolve schema by id: {_e2}")
                        if dashboard_visual is not None:
                            st.caption(f"Schema for ({ident_used})")
                            st.graphviz_chart(dashboard_visual)
                        else:
                            st.warning("Could not render dashboard schema. Tried by title and id.")
                    except Exception as _e:
                        st.error(f"Error rendering dashboard schema: {_e}")
            else:
                st.info("No dashboards found in this workspace.")

        with tab_filters:
            st.subheader("Filter Contexts")
            # Prefer dedicated filter contexts dataframe from cache; fallback to dashboard-derived aggregation
            fctx_df_cached = cache_entry.get("filter_ctx_df", DataFrame())
            # If cached df missing expected columns, rebuild and update cache
            required_cols_fc = {"title", "created_at", "modified_at", "filter_count"}
            if (fctx_df_cached is None) or fctx_df_cached.empty or not required_cols_fc.issubset(set(fctx_df_cached.columns)):
                try:
                    pre_filter_ctx_rows, _ = build_filter_context_rows_from_analytics(analytics)
                    fctx_df_cached = DataFrame(pre_filter_ctx_rows)
                    # update cache so subsequent renders use enriched columns
                    cache_entry = st.session_state.get("ws_cache", {}).get(st.session_state.get("current_ws_id"), None)
                    if isinstance(cache_entry, dict):
                        cache_entry["filter_ctx_df"] = fctx_df_cached
                except Exception:
                    pass
            if fctx_df_cached is not None and not fctx_df_cached.empty:
                df = fctx_df_cached.copy()
                # Expand definition to columns (prefix def.) if present
                if "definition" in df.columns:
                    try:
                        expl = DataFrame([_flatten_dict(x if isinstance(x, dict) else {}) for x in df["definition"].tolist()])
                        expl = expl.add_prefix("def.")
                        df = df.drop(columns=["definition"]).join(expl)
                    except Exception:
                        pass
                st.dataframe(df, width='stretch')
            else:
                # Build from dashboards dataframe if available; aggregate unique FCs
                df_dash = dashes_df.copy()
                if not df_dash.empty and "filter_context_id" in df_dash.columns:
                    # Keep only rows with FC ids
                    fcs = df_dash[df_dash["filter_context_id"].astype(str).str.len() > 0][["filter_context_id", "filter_context_definition", "title", "id"]].copy() if "filter_context_definition" in df_dash.columns else df_dash[["filter_context_id", "title", "id"]].copy()
                    # Group by id; if definition dict present, take first
                    try:
                        fcs = fcs.dropna(subset=["filter_context_id"]).groupby("filter_context_id").first().reset_index()
                    except Exception:
                        pass
                    # If definition is dict, expand a few common keys
                    if "filter_context_definition" in fcs.columns:
                        try:
                            # Normalize dict column into prefixed columns
                            expl = DataFrame([_flatten_dict(x if isinstance(x, dict) else {}) for x in fcs["filter_context_definition"].tolist()])
                            expl = expl.add_prefix("def.")
                            fcs = fcs.drop(columns=["filter_context_definition"]).join(expl)
                        except Exception:
                            pass
                    st.dataframe(fcs, width='stretch')
                else:
                    st.info("No filter contexts discovered from dashboards.")

        with tab_ldm:
            st.subheader("Logical Data Model")
            # Always use cached bundle; include best-effort data source enrichment if present
            ds_df = cache_entry.get("ldm_ds_df", DataFrame())
            cols_df = cache_entry.get("ldm_cols_df", DataFrame())
            refs_df = cache_entry.get("ldm_refs_df", DataFrame())
            fetched_via = "cache"
            # Multiselect datasets to filter columns
            if not ds_df.empty:
                ds_labels = (ds_df["dataset_title"].fillna(ds_df["dataset_id"]) if "dataset_title" in ds_df.columns else ds_df["dataset_id"]).tolist()
                default_selection = ds_labels
                selected_datasets = st.multiselect("Select datasets", options=ds_labels, default=default_selection)
                # map labels back to ids
                map_title_to_id = {row["dataset_title"] if row.get("dataset_title") else row.get("dataset_id"): row.get("dataset_id") for _, row in ds_df.fillna("").iterrows()}
                selected_ids = [map_title_to_id.get(lbl, lbl) for lbl in selected_datasets]
                if not cols_df.empty and selected_ids:
                    cols_df = cols_df[cols_df["dataset_id"].isin(selected_ids)]
            # Show datasource columns if available
            if "data_source_id" in ds_df.columns or "data_source_name" in ds_df.columns:
                st.caption("Datasets include best-effort data source mapping (via PDM table heuristics).")
            st.caption(f"Columns (via {fetched_via})")
            st.dataframe(cols_df, width='stretch')
            if refs_df is not None and not refs_df.empty:
                st.caption("References (dataset foreign keys)")
                st.dataframe(refs_df, width='stretch')

        with tab_graph:
            st.subheader("Dependent Entities Graph")
            try:
                components.html(html_cytoscape(st.session_state["gd"].ws_schema(active_ws.id)), height=650)
            except Exception as e:
                st.error(f"Failed to render graph: {e}")


if __name__ == "__main__":
    main()
