from dotenv import dotenv_values
# import FPDF
from gooddata_sdk import (GoodDataSdk, CatalogDeclarativeDashboardPermissionsForAssignee,
                          CatalogAssigneeRule, CatalogAssigneeIdentifier, CatalogPermissionsForAssigneeRule,
                          CatalogWorkspace, CatalogUser, CatalogUserGroup,
                          CatalogPermissionAssignments, CatalogWorkspacePermissionAssignment,
                          CatalogDataSourcePermissionAssignment,
                          CatalogPermissionsForAssigneeIdentifier)
from gooddata_pandas import GoodPandas
from json import dumps
import csv
from typing import Any, Dict, List, Optional
import math
from pandas import read_csv
from pathlib import Path
from tabulate import tabulate
from treelib import Tree
import requests


class GoodDataSemantics:
    """View-oriented semantic helpers built on top of the thin SDK wrapper."""

    def __init__(self, wrapper: "LoadGoodDataSdk"):
        self.wrapper = wrapper

    def _sdk_obj_to_dict(self, item: Any) -> dict:
        if isinstance(item, dict):
            return item
        if hasattr(item, "to_dict"):
            try:
                return item.to_dict()
            except Exception:
                pass
        return getattr(item, "__dict__", {}) or {}

    def _pick_semantic_value(self, data: Any, *paths: tuple) -> Any:
        for path in paths:
            current = data
            found = True
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    found = False
                    break
            if found and current not in (None, "", [], {}):
                return current
        return None

    @staticmethod
    def _safe_label(value: Any, fallback: str = "N/A") -> str:
        if value in (None, "", [], {}):
            return fallback
        return str(value)

    def _extract_filter_contexts(self, analytics: Any) -> list:
        if hasattr(analytics, "filter_contexts"):
            return getattr(analytics, "filter_contexts") or []
        if hasattr(analytics, "filterContexts"):
            return getattr(analytics, "filterContexts") or []
        analytics_dict = self._sdk_obj_to_dict(analytics)
        return analytics_dict.get("filter_contexts") or analytics_dict.get("filterContexts") or []

    def _collect_dashboard_share_records(
        self,
        workspace_id: str,
        dashboards: list,
        fallback_workspace_id: Optional[str] = None,
    ) -> dict:
        share_map = {}

        def load_permissions(target_workspace_id: str, dashboard_id: str):
            permissions = self.wrapper.list_dashboard_permissions(
                workspace_id=target_workspace_id,
                dashboard_id=dashboard_id,
            )
            permission_items = (
                getattr(permissions, "permissions_for_assignee", None)
                or getattr(permissions, "permissions_for_assignees", None)
                or []
            )
            if not permission_items and hasattr(permissions, "to_dict"):
                permission_dict = permissions.to_dict()
                permission_items = (
                    permission_dict.get("permissions_for_assignee")
                    or permission_dict.get("permissions_for_assignees")
                    or []
                )
            return permission_items

        def normalize_permission_item(item: Any, item_workspace_id: str):
            item_dict = self._sdk_obj_to_dict(item)
            identifier = getattr(item, "assignee_identifier", None)
            if identifier is None:
                identifier = (
                    self._pick_semantic_value(
                        item_dict,
                        ("assignee_identifier",),
                        ("assigneeIdentifier",),
                    )
                    or {}
                )
            if not isinstance(identifier, dict):
                identifier = self._sdk_obj_to_dict(identifier)

            assignee_id = (
                identifier.get("id")
                or getattr(getattr(item, "assignee_identifier", None), "id", None)
            )
            assignee_type = (
                identifier.get("type")
                or getattr(getattr(item, "assignee_identifier", None), "type", None)
            )

            permissions_list = getattr(item, "permissions", None)
            if permissions_list is None:
                permissions_list = item_dict.get("permissions") or []
            if not isinstance(permissions_list, list):
                permissions_list = [permissions_list]

            if not assignee_id or not assignee_type:
                return None

            return {
                "assignee_id": assignee_id,
                "assignee_type": assignee_type,
                "permissions": [str(p) for p in permissions_list if p not in (None, "")],
                "workspace_id": item_workspace_id,
            }

        for dashboard in dashboards:
            dashboard_id = getattr(dashboard, "id", None)
            if not dashboard_id:
                continue
            permission_items = []
            dashboard_workspace_id = workspace_id
            try:
                permission_items = load_permissions(dashboard_workspace_id, dashboard_id)
                if not permission_items and fallback_workspace_id and fallback_workspace_id != workspace_id:
                    dashboard_workspace_id = fallback_workspace_id
                    permission_items = load_permissions(dashboard_workspace_id, dashboard_id)
                normalized = []
                for item in permission_items:
                    normalized_item = normalize_permission_item(item, dashboard_workspace_id)
                    if normalized_item:
                        normalized.append(normalized_item)
                share_map[dashboard_id] = normalized
            except Exception:
                share_map[dashboard_id] = []
        return share_map

    def _extract_widget_refs_from_dashboard(self, dashboard: Any) -> list:
        dashboard_dict = self._sdk_obj_to_dict(dashboard)
        content = dashboard_dict.get("content") or getattr(dashboard, "content", {}) or {}
        layout = content.get("layout", {}) if isinstance(content, dict) else {}
        refs = []
        if not isinstance(layout, dict):
            return refs

        def walk_sections(sections, tab_index=None, tab_id=None, tab_title=None, tab_filters=None):
            for section_index, section in enumerate(sections or []):
                if not isinstance(section, dict):
                    continue
                header = section.get("header", {})
                section_title = header.get("title") if isinstance(header, dict) else section.get("title")
                items = section.get("items") or section.get("widgets") or []
                for item_index, item in enumerate(items):
                    if not isinstance(item, dict):
                        continue
                    widget = item.get("widget") or item
                    if not isinstance(widget, dict):
                        continue
                    # YAML layouts commonly use visualization directly instead
                    # of the API's nested widget/ref representation.
                    visualization = widget.get("visualization") or widget.get("insight")
                    if visualization and not widget.get("ref") and not widget.get("insightRef"):
                        widget = {
                            **widget,
                            "type": "insight",
                            "ref": visualization if isinstance(visualization, dict) else {"id": visualization},
                        }
                    refs.append({
                        "tab_index": tab_index,
                        "tab_id": tab_id,
                        "tab_title": tab_title,
                        "tab_filters": tab_filters or [],
                        "section_index": section_index,
                        "section_title": section_title,
                        "item_index": item_index,
                        "widget_type": widget.get("type"),
                        "visualization_id": self._pick_semantic_value(
                            widget,
                            ("ref", "id"),
                            ("ref", "identifier"),
                            ("insightRef", "id"),
                            ("insightRef", "identifier"),
                            ("identifier",),
                        ),
                        "title": widget.get("title"),
                    })

        tabs = layout.get("tabs") or []
        for tab_index, tab in enumerate(tabs):
            if not isinstance(tab, dict):
                continue
            tab_ref = tab.get("id") or tab.get("identifier") or {}
            tab_id = tab_ref.get("id") if isinstance(tab_ref, dict) else tab_ref
            tab_id = tab_id or f"tab-{tab_index + 1}"
            tab_title = tab.get("title") or tab.get("name") or tab_id
            tab_filters = tab.get("filters") or tab.get("filterContext") or []
            tab_layout = tab.get("layout") if isinstance(tab.get("layout"), dict) else tab
            walk_sections(
                tab_layout.get("sections", []) if isinstance(tab_layout, dict) else [],
                tab_index=tab_index,
                tab_id=str(tab_id),
                tab_title=tab_title,
                tab_filters=tab_filters if isinstance(tab_filters, list) else [tab_filters],
            )

        # Dashboards without native tabs keep their sections at the root.
        walk_sections(layout.get("sections", []))
        return refs

    def _extract_dashboard_tabs(self, dashboard: Any) -> list:
        dashboard_dict = self._sdk_obj_to_dict(dashboard)
        content = dashboard_dict.get("content") or getattr(dashboard, "content", {}) or {}
        layout = content.get("layout", {}) if isinstance(content, dict) else {}
        tabs = layout.get("tabs", []) if isinstance(layout, dict) else []
        result = []
        for index, tab in enumerate(tabs or []):
            if not isinstance(tab, dict):
                continue
            tab_ref = tab.get("id") or tab.get("identifier") or {}
            tab_id = tab_ref.get("id") if isinstance(tab_ref, dict) else tab_ref
            tab_id = tab_id or f"tab-{index + 1}"
            result.append({
                "index": index,
                "id": str(tab_id),
                "title": tab.get("title") or tab.get("name") or str(tab_id),
                "filters": tab.get("filters") or tab.get("filterContext") or [],
            })
        return result

    def _extract_visualization_semantics(self, visualization: Any) -> dict:
        visualization_dict = self._sdk_obj_to_dict(visualization)
        content = visualization_dict.get("content") or getattr(visualization, "content", {}) or {}
        measures = []
        attributes = []
        filters = []

        def walk(node: Any):
            if isinstance(node, dict):
                for key, value in node.items():
                    key_lower = str(key).lower()
                    if key_lower in {"measure", "measures"}:
                        measures.append(value)
                    elif key_lower in {"attribute", "attributes"}:
                        attributes.append(value)
                    elif "filter" in key_lower:
                        filters.append(value)
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(content)

        return {
            "id": visualization_dict.get("id", getattr(visualization, "id", None)),
            "title": visualization_dict.get("title", getattr(visualization, "title", "")),
            "description": visualization_dict.get("description", getattr(visualization, "description", "")),
            "content": content if isinstance(content, dict) else {},
            "afm": {
                "measures": measures,
                "attributes": attributes,
                "filters": filters,
            },
        }

    def collect_workspace_semantics(self, workspace_id: str) -> dict:
        workspace = self.wrapper.specific(workspace_id, of_type="workspace", by="id")
        analytics = self.wrapper.details(wks_id=workspace_id, by="id")
        dependency_graph = self.wrapper._sdk.catalog_workspace_content.get_dependent_entities_graph(workspace_id)

        dashboards = list(getattr(analytics, "analytical_dashboards", []) or [])
        visualizations = list(getattr(analytics, "visualization_objects", []) or [])
        metrics = list(getattr(analytics, "metrics", []) or [])
        filter_contexts = list(self._extract_filter_contexts(analytics) or [])

        dashboard_records = []
        for dashboard in dashboards:
            dashboard_dict = self._sdk_obj_to_dict(dashboard)
            dashboard_records.append({
                "id": dashboard_dict.get("id", getattr(dashboard, "id", None)),
                "title": dashboard_dict.get("title", getattr(dashboard, "title", "")),
                "description": dashboard_dict.get("description", getattr(dashboard, "description", "")),
                "widgets": self._extract_widget_refs_from_dashboard(dashboard),
                "tabs": self._extract_dashboard_tabs(dashboard),
                "raw": dashboard_dict,
            })

        visualization_records = [
            self._extract_visualization_semantics(visualization)
            for visualization in visualizations
        ]

        metric_records = []
        for metric in metrics:
            metric_dict = self._sdk_obj_to_dict(metric)
            metric_records.append({
                "id": metric_dict.get("id", getattr(metric, "id", None)),
                "title": metric_dict.get("title", getattr(metric, "title", "")),
                "description": metric_dict.get("description", getattr(metric, "description", "")),
                "raw": metric_dict,
            })

        filter_context_records = []
        for filter_context in filter_contexts:
            filter_context_dict = self._sdk_obj_to_dict(filter_context)
            content = filter_context_dict.get("content") or getattr(filter_context, "content", {}) or {}
            if hasattr(content, "to_dict"):
                try:
                    content = content.to_dict()
                except Exception:
                    content = getattr(content, "__dict__", {}) or {}
            filter_context_records.append({
                "id": filter_context_dict.get("id", getattr(filter_context, "id", None)),
                "title": filter_context_dict.get("title", getattr(filter_context, "title", "")),
                "description": filter_context_dict.get("description", getattr(filter_context, "description", "")),
                "filters": self._pick_semantic_value(content, ("filters",), ("filter",)) or [],
                "raw": filter_context_dict,
            })

        dependency_nodes = []
        for node in dependency_graph.graph.nodes:
            dependency_nodes.append({
                "id": getattr(node, "id", None),
                "label": getattr(node, "title", None),
                "type": getattr(node, "type", None),
            })
        dependency_edges = []
        for edge in dependency_graph.graph.edges:
            source, target = edge
            dependency_edges.append({
                "source": getattr(source, "id", None),
                "target": getattr(target, "id", None),
            })

        return {
            "workspace": {
                "id": getattr(workspace, "id", workspace_id),
                "name": getattr(workspace, "name", workspace_id),
                "parent_id": getattr(workspace, "parent_id", None),
            },
            "dashboards": dashboard_records,
            "visualizations": visualization_records,
            "metrics": metric_records,
            "filter_contexts": filter_context_records,
            "dependencies": {
                "nodes": dependency_nodes,
                "edges": dependency_edges,
            },
            "dashboard_shares": self._collect_dashboard_share_records(
                workspace_id,
                dashboards,
                fallback_workspace_id=getattr(workspace, "parent_id", None),
            ),
            "workspace_assignments": [],
        }

    def build_graph_elements(
        self,
        semantics: dict,
        mode: str = "workspace_dependencies",
        dashboard_id: Optional[str] = None,
    ) -> str:
        elements = []
        seen_nodes = set()
        seen_edges = set()

        def add_node(node_id: str, label: str, node_type: str, **extra):
            if not node_id or node_id in seen_nodes:
                return
            seen_nodes.add(node_id)
            data = {"id": node_id, "label": self._safe_label(label, node_id), "type": node_type}
            data.update({k: v for k, v in extra.items() if v not in (None, "", [], {})})
            elements.append({"data": data})

        def add_edge(source: str, target: str, edge_type: str = "relates_to", **extra):
            if not source or not target:
                return
            key = (source, target, edge_type)
            if key in seen_edges:
                return
            seen_edges.add(key)
            data = {"source": source, "target": target, "type": edge_type}
            data.update({k: v for k, v in extra.items() if v not in (None, "", [], {})})
            elements.append({"data": data})

        workspace = semantics.get("workspace", {})
        workspace_node_id = f"workspace:{workspace.get('id')}"
        add_node(workspace_node_id, workspace.get("name") or workspace.get("id"), "workspace")

        if mode == "workspace_dependencies":
            for node in semantics.get("dependencies", {}).get("nodes", []):
                source_node_id = node.get("id")
                if not source_node_id:
                    continue
                clean_node_id = source_node_id.split(".")[0] if "." in source_node_id else source_node_id
                add_node(clean_node_id, node.get("label") or clean_node_id, node.get("type") or "entity")
            for edge in semantics.get("dependencies", {}).get("edges", []):
                source = edge.get("source")
                target = edge.get("target")
                if source and "." in source:
                    source = source.split(".")[0]
                if target and "." in target:
                    target = target.split(".")[0]
                add_edge(source, target, "depends_on")

        elif mode == "dashboard_layout":
            for dashboard in semantics.get("dashboards", []):
                if dashboard_id and dashboard.get("id") != dashboard_id:
                    continue
                dashboard_node_id = f"dashboard:{dashboard.get('id')}"
                add_node(dashboard_node_id, dashboard.get("title") or dashboard.get("id"), "analyticalDashboard")
                add_edge(workspace_node_id, dashboard_node_id, "contains")
                tab_nodes = {}
                for tab in dashboard.get("tabs", []):
                    tab_node_id = f"{dashboard_node_id}:tab:{tab.get('id') or tab.get('index')}"
                    tab_nodes[tab.get("index")] = tab_node_id
                    add_node(tab_node_id, tab.get("title") or tab.get("id"), "dashboardTab")
                    add_edge(dashboard_node_id, tab_node_id, "contains")
                    for filter_index, filter_item in enumerate(tab.get("filters", []) or []):
                        filter_node_id = f"{tab_node_id}:filter:{filter_index}"
                        add_node(filter_node_id, self._safe_label(filter_item, f"Filter {filter_index + 1}")[:80], "filter")
                        add_edge(tab_node_id, filter_node_id, "contains")
                for widget in dashboard.get("widgets", []):
                    section_title = widget.get("section_title") or f"Section {widget.get('section_index', 0) + 1}"
                    tab_node_id = tab_nodes.get(widget.get("tab_index"))
                    section_prefix = tab_node_id or dashboard_node_id
                    section_node_id = f"{section_prefix}:section:{widget.get('section_index', 0)}"
                    add_node(section_node_id, section_title, "dashboardSection")
                    add_edge(tab_node_id or dashboard_node_id, section_node_id, "contains")
                    widget_type = widget.get("widget_type") or "widget"
                    viz_ref = widget.get("visualization_id")
                    widget_node_id = f"{section_node_id}:item:{widget.get('item_index', 0)}"
                    if widget_type == "insight" and viz_ref:
                        widget_node_id = f"visualization:{viz_ref}"
                    add_node(widget_node_id, widget.get("title") or viz_ref or widget_type, "visualizationObject" if widget_type == "insight" else widget_type)
                    add_edge(section_node_id, widget_node_id, "contains")

        elif mode == "dashboard_lineage":
            dependency_nodes = {
                node.get("id"): node for node in semantics.get("dependencies", {}).get("nodes", [])
            }
            dependency_edges = semantics.get("dependencies", {}).get("edges", [])
            visualization_ids = set()
            for dashboard in semantics.get("dashboards", []):
                if dashboard_id and dashboard.get("id") != dashboard_id:
                    continue
                dashboard_node_id = f"dashboard:{dashboard.get('id')}"
                add_node(dashboard_node_id, dashboard.get("title") or dashboard.get("id"), "analyticalDashboard")
                add_edge(workspace_node_id, dashboard_node_id, "contains")
                for widget in dashboard.get("widgets", []):
                    viz_ref = widget.get("visualization_id")
                    if not viz_ref:
                        continue
                    visualization_ids.add(viz_ref)
                    add_node(f"visualization:{viz_ref}", widget.get("title") or viz_ref, "visualizationObject")
                    add_edge(dashboard_node_id, f"visualization:{viz_ref}", "contains")
            related_ids = set(visualization_ids)
            changed = True
            while changed:
                changed = False
                for edge in dependency_edges:
                    source = edge.get("source")
                    target = edge.get("target")
                    if source in related_ids and target not in related_ids:
                        related_ids.add(target)
                        changed = True
                    if target in related_ids and source not in related_ids:
                        related_ids.add(source)
                        changed = True
            for node_id in related_ids:
                node = dependency_nodes.get(node_id) or dependency_nodes.get(node_id.split(".")[0]) or {}
                clean_node_id = node_id.split(".")[0] if "." in node_id else node_id
                add_node(clean_node_id, node.get("label") or clean_node_id, node.get("type") or "entity")
            for edge in dependency_edges:
                source = edge.get("source")
                target = edge.get("target")
                clean_source = source.split(".")[0] if source and "." in source else source
                clean_target = target.split(".")[0] if target and "." in target else target
                if clean_source in seen_nodes and clean_target in seen_nodes:
                    add_edge(clean_source, clean_target, "depends_on")

        elif mode == "filter_contexts":
            for filter_context in semantics.get("filter_contexts", []):
                fc_node_id = f"filterContext:{filter_context.get('id')}"
                add_node(fc_node_id, filter_context.get("title") or filter_context.get("id"), "filterContext")
                add_edge(workspace_node_id, fc_node_id, "contains")
                for index, filter_item in enumerate(filter_context.get("filters", [])):
                    filter_label = self._safe_label(filter_item, f"Filter {index + 1}")
                    filter_node_id = f"{fc_node_id}:filter:{index}"
                    add_node(filter_node_id, filter_label[:80], "filter")
                    add_edge(fc_node_id, filter_node_id, "contains")

        elif mode == "shares":
            for dashboard in semantics.get("dashboards", []):
                if dashboard_id and dashboard.get("id") != dashboard_id:
                    continue
                dash_node_id = f"dashboard:{dashboard.get('id')}"
                add_node(dash_node_id, dashboard.get("title") or dashboard.get("id"), "analyticalDashboard")
                add_edge(workspace_node_id, dash_node_id, "contains")
                for share in semantics.get("dashboard_shares", {}).get(dashboard.get("id"), []):
                    assignee_id = share.get("assignee_id")
                    assignee_type = share.get("assignee_type") or "assignee"
                    if not assignee_id:
                        continue
                    assignee_node_id = f"{assignee_type}:{assignee_id}"
                    add_node(assignee_node_id, assignee_id, assignee_type)
                    add_edge(assignee_node_id, dash_node_id, "shared_with", permissions=", ".join(share.get("permissions", [])))

        return dumps(elements)

    def _catalog_obj_to_dict(self, item):
        if isinstance(item, dict):
            return item
        if hasattr(item, "to_dict"):
            try:
                return item.to_dict()
            except Exception:
                pass
        return getattr(item, "__dict__", {}) or {}

    def _get_first_nested_value(self, data, *paths):
        for path in paths:
            current = data
            found = True
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    found = False
                    break
            if found and current not in (None, "", [], {}):
                return current
        return None

    def _normalize_automation_dict(self, automation):
        raw = self._catalog_obj_to_dict(automation)
        attrs = raw.get("attributes", raw) if isinstance(raw, dict) else {}
        if not isinstance(attrs, dict):
            attrs = {}
        return {
            "id": raw.get("id", getattr(automation, "id", "N/A")),
            "attributes": attrs,
        }

    def _looks_like_alert(self, attrs):
        if not isinstance(attrs, dict):
            return False
        type_value = str(
            self._get_first_nested_value(
                attrs,
                ("type",),
                ("kind",),
                ("automationType",),
                ("alert", "type"),
                ("metadata", "type"),
            ) or ""
        ).lower()
        if "alert" in type_value:
            return True
        alert_signals = [
            ("threshold",),
            ("condition",),
            ("trigger",),
            ("evaluation",),
            ("metric",),
            ("metricAlert",),
            ("alert",),
        ]
        return any(self._get_first_nested_value(attrs, signal) is not None for signal in alert_signals)

    def _looks_like_schedule(self, attrs):
        if not isinstance(attrs, dict):
            return False
        type_value = str(
            self._get_first_nested_value(
                attrs,
                ("type",),
                ("kind",),
                ("automationType",),
                ("schedule", "type"),
                ("metadata", "type"),
            ) or ""
        ).lower()
        if "schedule" in type_value:
            return True
        schedule_signals = [
            ("cron",),
            ("timezone",),
            ("recurrence",),
            ("schedule",),
            ("notificationChannel",),
            ("notificationChannelId",),
            ("export",),
        ]
        return any(self._get_first_nested_value(attrs, signal) is not None for signal in schedule_signals)

    def _automations_to_schedule_dicts(self, automations, user_id: str = None):
        out = []
        for automation in automations:
            normalized = self._normalize_automation_dict(automation)
            attrs = normalized["attributes"]
            if self._looks_like_schedule(attrs) or not self._looks_like_alert(attrs):
                out.append(normalized)
        return out

    def _automations_to_alert_dicts(self, automations, user_id: str = None):
        out = []
        for automation in automations:
            normalized = self._normalize_automation_dict(automation)
            if self._looks_like_alert(normalized["attributes"]):
                out.append(normalized)
        return out

    def get_user_schedules(self, user_id: str, workspace_id: str = None):
        try:
            wks_id = workspace_id or (self.wrapper.workspaces[0].id if self.wrapper.workspaces else None)
            if not wks_id:
                return []
            automations = self.wrapper.get_declarative_automations(wks_id)
            return self._automations_to_schedule_dicts(automations, user_id)
        except Exception as exc:
            print(f"Error getting schedules for user {user_id}: {str(exc)}")
            return []

    def get_user_alerts(self, user_id: str, workspace_id: str = None):
        try:
            wks_id = workspace_id or (self.wrapper.workspaces[0].id if self.wrapper.workspaces else None)
            if not wks_id:
                return []
            automations = self.wrapper.get_declarative_automations(wks_id)
            return self._automations_to_alert_dicts(automations, user_id)
        except Exception as exc:
            print(f"Error getting alerts for user {user_id}: {str(exc)}")
            return []

    def get_user_automations(self, user_id: str, workspace_id: str = None):
        return {
            "schedules": self.get_user_schedules(user_id, workspace_id),
            "alerts": self.get_user_alerts(user_id, workspace_id),
        }

    def get_workspace_automations(self, workspace_id: str = None):
        wks_id = workspace_id or (self.wrapper.workspaces[0].id if self.wrapper.workspaces else None)
        if not wks_id:
            return {"schedules": [], "alerts": []}
        try:
            automations = self.wrapper.get_declarative_automations(wks_id)
            return {
                "schedules": self._automations_to_schedule_dicts(automations),
                "alerts": self._automations_to_alert_dicts(automations),
            }
        except Exception as exc:
            print(f"Error getting workspace automations: {str(exc)}")
            return {"schedules": [], "alerts": []}


class LoadGoodDataSdk:
    # abstract level wrapper for GoodData Python SDK
    def __init__(self, gd_host: str = "", gd_token: str = ""):
        print(
            "--- Using SEE monkey-patched GoodData wrapper ---"
            "Your workspace environment variables:\n",
            f"GOODDATA_HOST: {gd_host} / GOODDATA_TOKEN: {len(gd_token)} characters",
        )
        if gd_host:
            self._host = gd_host.rstrip('/')
            self._token = gd_token
            self._sdk = GoodDataSdk.create(gd_host, gd_token)
            self._gp = GoodPandas(gd_host, gd_token)
            self.semantics = GoodDataSemantics(self)
            self._df = None
            self.workspaces = self._sdk.catalog_workspace.list_workspaces()
            try:
                self.users = (
                    self._sdk.catalog_user.list_users()
                )  # alternative get_declarative_users()
                self.groups = self._sdk.catalog_user.list_user_groups()
                self.datasources = self._sdk.catalog_data_source.list_data_sources()
                self.admin = True
            except Exception as ex:
                self.admin = False
                print(ex)
        else:
            self._host = ""
            self._token = ""
            self.semantics = GoodDataSemantics(self)

    @property
    def sdk(self):
        """Backward-compatible access to the underlying GoodData SDK."""
        return getattr(self, "_sdk", None)

    def clear_cache(self, ds_id: str):
        if ds_id:
            self._sdk.catalog_data_source.register_upload_notification(data_source_id=ds_id)
        else:
            print("no datasource id submitted...")

    def create(self, ent_id: str, name: str = "", of_type: str = "ws", parent: str = ""):
        if of_type == 'ws':  # workspace
            self._sdk.catalog_workspace.create_or_update(
                CatalogWorkspace(workspace_id=ent_id, name=name, parent_id=parent)
            )
        elif of_type == 'us':  # user
            self._sdk.catalog_user.create_or_update_user(
                CatalogUser.init(user_id=ent_id, firstname=name.split(" ")[0], lastname=name.split(" ")[-1],
                                 user_group_ids=[parent])
            )
        elif of_type == 'ug':  # user group
            self._sdk.catalog_user.create_or_update_user_group(
                CatalogUserGroup.init(user_group_id=ent_id, user_group_name=name)
            )
        if of_type == 'wf':  # workspace filter
            self._sdk.catalog_workspace.create_or_update(
                CatalogWorkspace(workspace_id=ent_id, name=name, parent_id=parent)
            )
        elif of_type == 'uf':  # user filter
            self._sdk.catalog_user.create_or_update_user(
                CatalogUser.init(user_id=ent_id, firstname=name.split(" ")[0], lastname=name.split(" ")[-1],
                                 user_group_ids=[parent])
            )

    def data(self, ws_id="", vis_id="", pdf_export=False, path="", using_pandas=True):
        # returns data frame or pdf / must run details first
        if not vis_id:
            return self._gp.data_frames(ws_id)
        else:
            if pdf_export:
                dataframe_to_pdf(self._df.for_visualization(visualization_id=vis_id), pdf_path=path, num_pages=2)
            else:
                if using_pandas:
                    return self._df.for_visualization(visualization_id=vis_id)
                else:
                    x = self._sdk.visualizations.get_visualization(workspace_id=ws_id, visualization_id=vis_id)
                    return self._sdk.tables.for_visualization(workspace_id=ws_id, visualization=x)

    def details(self, wks_id: str = "", by: str = "id") -> []:
        # display details about workspace in detail (all objects within)
        if not wks_id:
            wks_id = self.first(of_type="workspace")
            print("selecting first workspace as no one submitted")
        if by != "id":
            wks_id = self.get_id(wks_id, of_type="workspace")
        self._df = self.data(ws_id=wks_id)
        return self._sdk.catalog_workspace_content.get_declarative_analytics_model(wks_id).analytics

    def export(self, wks_id: str = "", by: str = "id", vis_id: str = "", export_format: str = "",
               location: str = ""):
        # export workspace to a physical drive
        if not wks_id:
            wks_id = self.first(of_type="workspace")
            print(f"selecting first workspace (id: {wks_id}) as no one submitted")
        if by != "id":
            wks_id = self.get_id(wks_id, of_type="workspace")
        if export_format.lower() == "pdf":
            if vis_id:
                return self._sdk.export.export_tabular_by_visualization_id(vis_id, wks_id, "PDF", "insight_data")
            else:
                return self._sdk.export.export_pdf(wks_id, self.first("dashboard"), "Dashboard_1.pdf")
        elif export_format.lower() == "csv":
            if vis_id:
                return self._sdk.export.export_tabular_by_visualization_id(vis_id, wks_id, "CSV", "insight_data")
            else:
                return self._sdk.catalog_workspace_content.load_declarative_analytics_model(wks_id, Path(location))
        else:
            return self._sdk.catalog_workspace_content.load_declarative_analytics_model(wks_id, Path(location))

    def first(self, of_type="user", by="id"):
        if of_type == "user":
            return first_item(self.users, by)
        elif of_type == "group":
            return first_item(self.groups, by)
        elif of_type == "datasource":
            return first_item(self.datasources, by)
        elif of_type == "dashboard":
            analytics = self.details(first_item(self.workspaces, by))
            return first_item(analytics.analytical_dashboards, by)
        elif of_type == "workspace":
            return first_item(self.workspaces, by)

    def get_id(self, name, of_type, main=""):
        if not name:
            return None
        if of_type == "user":
            # Construct user display name from available attributes for matching
            for u in self.users:
                user_name = getattr(u, 'name', None)
                if not user_name:
                    # Try firstname + lastname
                    firstname = getattr(u, 'firstname', None) or getattr(u, 'first_name', None)
                    lastname = getattr(u, 'lastname', None) or getattr(u, 'last_name', None)
                    if firstname or lastname:
                        user_name = f"{firstname or ''} {lastname or ''}".strip()
                if not user_name:
                    # Try email
                    user_name = getattr(u, 'email', None) or getattr(u, 'login', None)
                if not user_name:
                    # Fallback to ID
                    user_name = u.id
                if name == user_name or name == u.id:
                    return u.id
            return None
        elif of_type == "group":
            return [g.id for g in self.groups if name == g.name][0]
        elif of_type == "datasource":
            return [d.id for d in self.datasources if name == d.name][0]
        elif of_type == "workspace":
            return [w.id for w in self.workspaces if name == w.name][0]
        else:
            temp = self.details(wks_id=main, by="id")
            if of_type == "insight":
                return [i.id for i in temp.visualization_objects if name == i.title][0]
            elif of_type == "dashboard":
                return [w.id for w in temp.analytical_dashboards if name == w.title][0]
            elif of_type == "metric":
                return [w.id for w in temp.metrics if name == w.title][0]

    def organization(self):
        # print(f"\nCurrent organization id:{self._sdk.catalog_organization.get_organization().id}")
        # pretty(self._sdk.catalog_organization.get_organization().to_dict())
        return self._sdk.catalog_organization.get_organization()

    def assign_permissions(
        self,
        entity_id: str,
        entity_type: str,
        level: int = 0,
        ws_id: str = None,
        ws_right: list[str] = None,
        ds_id: str = None,
        ds_right: list[str] = None,
        dashboard_id: str = None,
        dashboard_rights: list[str] = None
    ):
        """
        Assign permissions to a user or user group.

        :param entity_id: ID of the user or user group
        :param entity_type: 'user' or 'userGroup'
        :param level: 0 = workspace+DS level, 1 = dashboard level
        :param ws_id: Workspace ID
        :param ws_right: List of workspace permissions
        :param ds_id: Data source ID
        :param ds_right: List of data source permissions
        :param dashboard_id: Dashboard ID (required for level 1)
        :param dashboard_rights: Permissions to assign to dashboard
        """
        assignee_type = "user" if entity_type == "user" else "userGroup"

        if level == 0:
            perms = CatalogPermissionAssignments(
                workspaces=[CatalogWorkspacePermissionAssignment(id=ws_id, permissions=ws_right)] if ws_id and ws_right else [],
                data_sources=[CatalogDataSourcePermissionAssignment(id=ds_id, permissions=ds_right)] if ds_id and ds_right else [],
            )
            if assignee_type == "user":
                self._sdk.catalog_user.manage_user_permissions(entity_id, perms)
            else:
                self._sdk.catalog_user.manage_user_group_permissions(entity_id, perms)

        elif level == 1:
            if not dashboard_id or not dashboard_rights:
                raise ValueError("Dashboard ID and rights must be provided for level 1 dashboard permission assignment")

            dash_perm = CatalogPermissionsForAssigneeIdentifier(
                assignee_identifier=CatalogAssigneeIdentifier(id=entity_id, type=assignee_type),
                permissions=dashboard_rights
            )
            self._sdk.catalog_permission.manage_dashboard_permissions(
                workspace_id=ws_id,
                dashboard_id=dashboard_id,
                permissions_for_assignee=[dash_perm]
            )

    def share_dashboard(
        self,
        entity_id: str,
        entity_type: str,
        workspace_id: str,
        dashboard_id: str,
        permissions: list[str]
    ):
        """
        Share a dashboard with a user or user group by assigning permissions.

        :param entity_id: ID of the user or user group
        :param entity_type: 'user' or 'userGroup'
        :param workspace_id: Workspace where the dashboard resides
        :param dashboard_id: ID of the dashboard to share
        :param permissions: List of permissions to assign (e.g., ["SHARE"])
        """
        assignee_type = "user" if entity_type == "user" else "userGroup"

        dashboard_permission = CatalogPermissionsForAssigneeIdentifier(
            assignee_identifier=CatalogAssigneeIdentifier(
                id=entity_id,
                type=assignee_type
            ),
            permissions=permissions
        )

        self._sdk.catalog_permission.manage_dashboard_permissions(
            workspace_id=workspace_id,
            dashboard_id=dashboard_id,
            permissions_for_assignee=[dashboard_permission]
        )

    def assign_user_to_workspace(self, user_id: str, workspace_id: str, permissions: Optional[list[str]] = None):
        """
        Assign a user to a workspace with the provided permissions.
        """
        workspace_permissions = permissions or ["VIEW"]
        permission_assignment = CatalogPermissionAssignments(
            workspaces=[
                CatalogWorkspacePermissionAssignment(
                    id=workspace_id,
                    permissions=workspace_permissions,
                )
            ]
        )
        self._sdk.catalog_user.manage_user_permissions(user_id, permission_assignment)

    def create_or_update_user_group_simple(self, group_id: str, group_name: str = ""):
        """
        Create or update a user group using the SDK wrapper.
        """
        effective_name = group_name or group_id
        self._sdk.catalog_user.create_or_update_user_group(
            CatalogUserGroup.init(user_group_id=group_id, user_group_name=effective_name)
        )

    def create_or_update_user_simple(
        self,
        user_id: str,
        firstname: str = "",
        lastname: str = "",
        user_group_ids: Optional[list[str]] = None,
    ):
        """
        Create or update a user and attach the given user groups.
        """
        self._sdk.catalog_user.create_or_update_user(
            CatalogUser.init(
                user_id=user_id,
                firstname=firstname,
                lastname=lastname,
                user_group_ids=user_group_ids or [],
            )
        )

    def deploy_testing_users(self, workspace_id: str, users_data: dict) -> dict:
        """
        Create/update configured user groups and users, then assign users to a workspace.
        Returns a report structure for the UI layer.
        """
        result = {
            "groups": [],
            "users": [],
            "success_count": 0,
            "error_count": 0,
        }
        user_groups_list = users_data.get("userGroups", []) or []
        users_list = users_data.get("users", []) or []

        for group in user_groups_list:
            group_id = group.get("id", "")
            group_name = group.get("name", group_id)
            if not group_id:
                continue
            try:
                self.create_or_update_user_group_simple(group_id, group_name)
                result["groups"].append({
                    "group_id": group_id,
                    "group_name": group_name,
                    "success": True,
                    "message": f"Created/updated user group: {group_name}",
                })
            except Exception as e:
                result["groups"].append({
                    "group_id": group_id,
                    "group_name": group_name,
                    "success": False,
                    "message": f"Failed to create user group '{group_id}': {str(e)}",
                })

        for user in users_list:
            user_id = user.get("id", "")
            if not user_id:
                continue
            user_groups = user.get("userGroups", []) or []
            group_ids = [g.get("id", "") if isinstance(g, dict) else str(g) for g in user_groups if g]
            try:
                self.create_or_update_user_simple(
                    user_id=user_id,
                    firstname=user.get("firstname", ""),
                    lastname=user.get("lastname", ""),
                    user_group_ids=group_ids,
                )
                self.assign_user_to_workspace(user_id, workspace_id, ["VIEW"])
                result["users"].append({
                    "user_id": user_id,
                    "success": True,
                    "message": f"Created/updated user '{user_id}' and assigned to workspace",
                })
                result["success_count"] += 1
            except Exception as e:
                result["users"].append({
                    "user_id": user_id,
                    "success": False,
                    "message": f"Failed to create/update user '{user_id}': {str(e)}",
                })
                result["error_count"] += 1

        return result

    def list_dashboard_permissions(self, workspace_id: str, dashboard_id: str):
        """
        List users and user groups with permissions for a dashboard (dashboard shares).

        :param workspace_id: Workspace where the dashboard resides
        :param dashboard_id: ID of the dashboard
        :return: CatalogDashboardPermissions (assignees and their permissions)
        """
        return self._sdk.catalog_permission.list_dashboard_permissions(
            workspace_id=workspace_id,
            dashboard_id=dashboard_id
        )

    def specific(self, value, of_type="user", by="id", ws_id=""):
        # return specific object from semantic definition by its type
        if by != "id":
            value = self.get_id(value, of_type, main=ws_id)
            by = "id"
        if of_type == "user":
            return self._sdk.catalog_user.get_user(value)
        elif of_type == "group":
            return self._sdk.catalog_user.get_user_group(value)
        elif of_type == "datasource":
            return self._sdk.catalog_data_source.get_data_source(value)
        elif of_type == "workspace":
            return self._sdk.catalog_workspace.get_workspace(value)
        elif of_type == "dashboard":
            return [d for d in self.details(ws_id, by).analytical_dashboards if d.id == value][0]
        elif of_type == "insight":
            # return self._sdk.insights.get_insight(value)
            return self.data(ws_id=ws_id, vis_id=value)
        elif of_type == "metric":
            return [m for m in self._sdk.catalog_workspace_content.get_metrics_catalog(ws_id) if m.id == value][0]

    def tree(self, of_id: str = "") -> Tree:
        # gives you all node descendants or the whole structure (or of a specific id instead)
        tree = Tree()
        tree.create_node("Workspace list", "root")
        for workspace in self.workspaces:
            parent_id = workspace.parent_id if workspace.parent_id else "root"
            if of_id and of_id not in (workspace.parent_id, workspace.id):  # TODO: check if filters well
                continue  # searching only for valid descendants
            if tree.get_node(workspace.id):
                continue  # we already established the node
            elif tree.get_node(parent_id):
                tree.create_node(workspace.name, workspace.id, parent=parent_id)
            else:
                temp_root = self.specific(parent_id, of_type="workspace")
                temp_parent_id = temp_root.parent_id if temp_root.parent_id else "root"
                tree.create_node(temp_root.name, temp_root.id, parent=temp_parent_id)
                tree.create_node(workspace.name, workspace.id, parent=parent_id)
        # tree.show(line_type="ascii-em")
        return tree

    def collect_workspace_semantics(self, workspace_id: str) -> dict:
        return self.semantics.collect_workspace_semantics(workspace_id)

    def build_graph_elements(
        self,
        semantics: dict,
        mode: str = "workspace_dependencies",
        dashboard_id: Optional[str] = None,
    ) -> str:
        return self.semantics.build_graph_elements(semantics, mode=mode, dashboard_id=dashboard_id)

    def users_in_group(self, group_id):
        # return users that belong to a specific group
        listed = [user for user in self.users if user.relationships for group in user.relationships.user_groups.data if
                  group and group.id == group_id]
        return listed

    def get_declarative_notification_channels(self):
        """
        Get all declarative notification channels in the organization.
        Uses GoodData Python SDK: catalog_organization.get_declarative_notification_channels()
        https://www.gooddata.com/docs/python-sdk/latest/administration/notification-channels/get_declarative_notification_channels/

        :return: List of CatalogDeclarativeNotificationChannel
        """
        try:
            return self._sdk.catalog_organization.get_declarative_notification_channels()
        except Exception as e:
            print(f"Error getting declarative notification channels: {str(e)}")
            return []

    def get_declarative_automations(self, workspace_id: str):
        """
        Get all declarative automations for a workspace (schedules, alerts, etc.).
        Uses GoodData Python SDK: catalog_workspace.get_declarative_automations(workspace_id)
        https://www.gooddata.com/docs/python-sdk/latest/workspace/workspaces/get_declarative_automations/

        :param workspace_id: Workspace id, e.g. "demo"
        :return: List of CatalogDeclarativeAutomation
        """
        try:
            return self._sdk.catalog_workspace.get_declarative_automations(workspace_id=workspace_id)
        except Exception as e:
            print(f"Error getting declarative automations for workspace {workspace_id}: {str(e)}")
            return []

    def get_user_schedules(self, user_id: str, workspace_id: str = None):
        return self.semantics.get_user_schedules(user_id, workspace_id)

    def get_user_alerts(self, user_id: str, workspace_id: str = None):
        return self.semantics.get_user_alerts(user_id, workspace_id)

    def get_user_automations(self, user_id: str, workspace_id: str = None):
        return self.semantics.get_user_automations(user_id, workspace_id)

    def get_workspace_automations(self, workspace_id: str = None):
        return self.semantics.get_workspace_automations(workspace_id)


def pretty(d, indent=1, char="-"):
    for key, value in d.items():
        if isinstance(value, dict):
            pretty(value, indent + 2)
        else:
            print(f"{char * indent} {str(key)} : {str(value)}")


def first_item(dataset, attr=""):
    if len(dataset) < 1:
        return None
    else:
        return next(iter(dataset)).__getattribute__(attr)


def encapsulate(column_name: str):
    if not column_name.startswith('"') and not column_name.endswith('"'):
        return '"' + column_name + '"'
    else:
        return column_name


def dataframe_to_pdf(dataframe, pdf_path, num_pages):
    rows_per_page = math.ceil(len(dataframe) / num_pages)
    # pdf = FPDF()
    for page in range(num_pages):
        start_idx = page * rows_per_page
        end_idx = min((page + 1) * rows_per_page, len(dataframe))
        page_df = dataframe.iloc[start_idx:end_idx]
        # pdf.add_page()
        # Convert DataFrame to a formatted table
        table = tabulate(page_df, headers='keys', tablefmt='grid', showindex=False)
        # Add the table to the PDF
        # pdf.set_font("Arial", size=12)
        # pdf.multi_cell(0, 10, table)
    # Save the PDF
    # pdf.output(pdf_path)

def csv_to_sql(csv_filename, limit=200):
    # return single SQL query from CSV content
    df = read_csv(csv_filename)
    columns = df.columns
    # Construct the SQL query using list comprehension
    rows = [
        "SELECT "
        + ", ".join(
            [
                f"'{str(row[col])}' AS {encapsulate(col.strip())}"
                if isinstance(row[col], str)
                else f"{str(row[col])} AS {encapsulate(col.strip())}"
                for col in columns
            ]
        )
        for _, row in df.iterrows()
    ]
    # return the dictionary of the final SQL query and table_name
    return {"title": csv_filename, "query": " UNION ALL ".join(rows[:limit]) + ";"}


def generate_ldm_json_from_csv(csv_path: str,
                               dataset_id: str,
                               dataset_title: str = None,
                               description: str = None,
                               datasource_id: str = "my-postgres") -> Dict:
    """
    Generate a GoodData LDM JSON object from a CSV file with columns: name, dataType.
    PostgreSQL return query:
    SELECT table_name, column_name, data_type FROM information_schema.columns
    WHERE table_schema = 'doc' ORDER BY table_name, ordinal_position;

    Parameters:
    - csv_path (str): Path to the input CSV file.
    - dataset_id (str): ID for the dataset.
    - dataset_title (str, optional): Human-readable title. Defaults to dataset_id.title().
    - description (str, optional): Dataset description. Defaults to "Dataset for table {dataset_id}".
    - datasource_id (str): GoodData datasource identifier. Defaults to 'my-postgres'.

    Returns:
    - dict: JSON-compatible LDM structure with attributes, facts, labels, and SQL reference.
    """
    # Load CSV data
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        columns = [row for row in reader]

    # Set title and description defaults
    dataset_title = dataset_title or dataset_id.replace('_', ' ').title()
    description = description or f"Dataset for table '{dataset_id}'"
    grain_column = columns[0]["column_name"]

    # Prepare containers
    attributes = []
    attribute_field_types = ["INT", "STRING", "TIMESTAMP", "DATE", "TIMESTAMP_TZ", "BOOLEAN"]
    facts = []
    fact_field_types = ["NUMERIC"]

    for col in columns:
        name = col["column_name"]
        dtype = col["data_type"].upper()

        if any(substring in dtype.upper() for substring in ["DOUBLE", "FLOAT", "REAL", "NUMERIC"]):
            # Construct fact
            mapped_type = dtype if any(dtype == t for t in fact_field_types) else "NUMERIC"
            fact = {
                "id": f"fact.{dataset_id}.{name}",
                "title": name.replace('_', ' ').title(),
                "description": f"Fact for column {name}",
                "sourceColumn": name,
                "sourceColumnDataType": mapped_type,
                "tags": [dataset_id]
            }
            facts.append(fact)
        else:
            # Ensure valid GoodData-compatible type
            mapped_type = dtype if any(dtype == t for t in attribute_field_types) else "STRING"
            # All of other labels for now! (TODO: datetimes)
            attribute = {
                "id": f"attr.{dataset_id}.{name}",
                "title": name.replace('_', ' ').title(),
                "description": f"Attribute for column {name}",
                "labels": [
                    # {
                    #     "id": f"label.{name}",
                    #     "title": name.replace('_', ' ').title(),
                    #     "description": f"Label for {name}",
                    #     "sourceColumn": name,
                    #     "sourceColumnDataType": mapped_type,
                    #     "tags": [dataset_id],
                    #     "valueType": "TEXT"
                    # }
                ],
                "tags": [dataset_id],
                # "sortColumn": name,
                # "sortDirection": "ASC",
                # "defaultView": {
                #     "id": f"label.{name}",
                #     "type": "label"
                # },
                "sourceColumn": name,
                "sourceColumnDataType": mapped_type
            }
            attributes.append(attribute)

    # Compose full LDM body
    ldm = {
        "ldm": {
            "datasets": [
                {
                    "aggregatedFacts": [],
                    "attributes": attributes,
                    "dataSourceTableId": {
                        "dataSourceId": datasource_id,
                        "id": dataset_id,
                        "path": f"doc.{dataset_id}",
                        "type": "dataSource"
                    },
                    "description": description,
                    "facts": facts,
                    "grain": [
                        # {
                        #     "id": grain_column,
                        #     "type": "attribute"
                        # }
                    ],
                    "id": dataset_id,
                    "references": [],
                    "sql": {
                        "statement": f"SELECT * FROM {dataset_id}",
                        "dataSourceId": datasource_id
                    },
                    "tags": [dataset_id],
                    # "precedence": 0
                    "title": dataset_title
                    # "workspaceDataFilterColumns": [],
                    # "workspaceDataFilterReferences": [],
                }
            ],
            "dateInstances": [],
            # "datasetExtensions": []
        }
    }

    return ldm


def upload_csv_to_workspace(csv_path: Path, dataset_id: str, env_file: str,
                            workspace_id: str = None, data_source_id: str = None):
    """
    Upload a CSV file to GoodData workspace as a CSV data source dataset.

    Args:
        csv_path: Path to CSV file
        dataset_id: ID for the dataset
        env_file: Environment file name
        workspace_id: Workspace ID (optional, from env if not provided)
        data_source_id: Data source ID (optional, from env if not provided)
    """
    env_vars = read_env_file(env_file)

    host = env_vars.get("GOODDATA_HOST", "").rstrip("/")
    token = env_vars.get("GOODDATA_TOKEN", "")
    workspace_id = workspace_id or env_vars.get("GOODDATA_DEFAULT_WORKSPACE", "")
    data_source_id = data_source_id or env_vars.get("GOODDATA_DEFAULT_DATASOURCE", "")

    if not all([host, token, workspace_id, data_source_id]):
        raise ValueError("Missing required environment variables: GOODDATA_HOST, GOODDATA_TOKEN, "
                         "GOODDATA_DEFAULT_WORKSPACE, GOODDATA_DEFAULT_DATASOURCE")

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    print(f"📤 Uploading CSV: {csv_path.name}")
    print(f"   Dataset ID: {dataset_id}")
    print(f"   Workspace: {workspace_id}")
    print(f"   Data Source: {data_source_id}")

    # Step 1: Upload CSV file to data source
    upload_url = f"{host}/api/v1/actions/dataSources/{data_source_id}/upload"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    with open(csv_path, "rb") as f:
        files = {"file": (csv_path.name, f, "text/csv")}
        response = requests.post(upload_url, headers=headers, files=files)

    if response.status_code not in [200, 201, 204]:
        print(f"❌ Failed to upload CSV: {response.status_code}")
        print(response.text)
        return False

    print("✅ CSV uploaded successfully")

    # Step 2: Create dataset from uploaded CSV
    # Note: This is a simplified version. In practice, you may need to:
    # 1. Create the dataset definition
    # 2. Upload the logical data model
    # 3. Load data into the dataset

    print("💡 Next steps:")
    print(f"   1. Create dataset definition in analytics/datasets/{dataset_id}.yaml")
    print("   2. Use 'npm run deploy' to deploy the dataset")
    print("   3. Or use the GoodData API to create the dataset programmatically")

    return True


def init_gd(default_env: str = "test"):
    # Load environment variables from .env.* file stored in root directory
    temp = read_env_file(file_name_append=default_env)

    # Access the environment variables
    host = temp["GOODDATA_HOST"]
    token = temp["GOODDATA_TOKEN"]

    sdk = GoodDataSdk.create(host, token)

    return host, token, sdk


def create_motherduck_ds(default_env: str = "test"):
    # Load environment variables from .env.* file stored in root directory
    temp = read_env_file(file_name_append=default_env)

    # Access the environment variables
    motherduck_db_name = temp["MOTHERDUCK_DB_NAME"]
    motherduck_token = temp["MOTHERDUCK_TOKEN"]

    return motherduck_db_name, motherduck_token


def ensure_motherduck_datasource(
        host: str,
        token: str,
        ds_id: str = "motherduck-ds",
        jdbc_schema: str = "main"
):
    """
    Ensure the MotherDuck data source exists.

    Args:
        host (str): GoodData host URL.
        token (str): GoodData API token.
        ds_id (str): ID of the data source (default: "motherduck-ds").
        jdbc_schema (str): Schema to use in the DS config (default: "main").
    """
    import base64
    import requests

    print("\n🦆 Creating MotherDuck data source...")
    motherduck_db_name, motherduck_token = create_motherduck_ds()
    encoded_token = base64.b64encode(motherduck_token.encode("utf-8")).decode("utf-8")
    jdbc_url = f"jdbc:duckdb:md:{motherduck_db_name}"

    payload = {
        "data": {
            "type": "dataSource",
            "id": ds_id,
            "attributes": {
                "name": "MotherDuck Data Source",
                "type": "MOTHERDUCK",
                "url": jdbc_url,
                "token": encoded_token,
                "username": "",
                "schema": jdbc_schema
            }
        }
    }

    response = requests.post(
        f"{host}/api/v1/entities/dataSources",
        headers={
            "Content-Type": "application/vnd.gooddata.api+json",
            "Accept": "application/vnd.gooddata.api+json",
            "Authorization": f"Bearer {token}"
        },
        json=payload
    )

    if response.status_code < 210:
        print("✅ MotherDuck data source created successfully.")
    elif response.status_code == 400 and "already stored in database" in response.text:
        print("✅ MotherDuck data source already exists.")
    else:
        print(f"❌ Failed to create MotherDuck data source: {response.status_code}")
        print(response.text)


def ensure_datasource(host: str, token: str, ds_id: str, ds_type: str, name: str = None, **attrs):
    """
    Generic idempotent "ensure this data source exists" — POSTs a dataSource
    entity of the given type with whatever type-specific attributes (url,
    schema, username, password, token, ...) the caller passes in `attrs`.

    Args:
        host (str): GoodData host URL.
        token (str): GoodData API token.
        ds_id (str): ID of the data source.
        ds_type (str): GoodData data source type (e.g. "SNOWFLAKE", "POSTGRESQL", "MOTHERDUCK").
        name (str): Display name (default: ds_id).
        **attrs: type-specific attributes merged into the request (url, schema, username, password, token, ...).
    """
    payload = {
        "data": {
            "type": "dataSource",
            "id": ds_id,
            "attributes": {
                "name": name or ds_id,
                "type": ds_type.upper(),
                **attrs,
            }
        }
    }

    response = requests.post(
        f"{host}/api/v1/entities/dataSources",
        headers={
            "Content-Type": "application/vnd.gooddata.api+json",
            "Accept": "application/vnd.gooddata.api+json",
            "Authorization": f"Bearer {token}"
        },
        json=payload
    )

    if response.status_code < 210:
        print(f"✅ {ds_type.upper()} data source '{ds_id}' created successfully.")
    elif response.status_code == 400 and "already stored in database" in response.text:
        print(f"✅ {ds_type.upper()} data source '{ds_id}' already exists.")
    else:
        print(f"❌ Failed to create {ds_type.upper()} data source '{ds_id}': {response.status_code}")
        print(response.text)


def ensure_snowflake_datasource(
        host: str,
        token: str,
        ds_id: str,
        account: str,
        warehouse: str,
        db: str,
        schema: str,
        username: str,
        password: str,
        name: str = None,
):
    """
    Ensure a Snowflake data source exists (one entity, N tenant schemas can
    each be pointed at by a per-workspace `dataSource.schemaPath` override —
    see `set_workspace_data_source`).

    Args:
        host (str): GoodData host URL.
        token (str): GoodData API token.
        ds_id (str): ID of the data source.
        account (str): Snowflake account identifier (the `<account>` in `<account>.snowflakecomputing.com`).
        warehouse (str): Snowflake warehouse name.
        db (str): Snowflake database name.
        schema (str): Default schema for the data source entity itself.
        username (str): Snowflake username.
        password (str): Snowflake password.
        name (str): Display name (default: "Snowflake Data Source").
    """
    jdbc_url = f"jdbc:snowflake://{account}.snowflakecomputing.com?warehouse={warehouse}&db={db}"
    ensure_datasource(
        host, token, ds_id, "SNOWFLAKE",
        name=name or "Snowflake Data Source",
        url=jdbc_url,
        schema=schema,
        username=username,
        password=password,
    )


def set_workspace_data_source(
        host: str,
        token: str,
        workspace_id: str,
        name: str,
        data_source_id: str,
        schema_path: list,
        parent_id: str = None,
):
    """
    Bind a workspace to its own data source + schema — GoodData's "unique
    data sources for tenants" (see
    https://www.gooddata.ai/docs/cloud/workspaces/workspaces-layout/#unique-data-sources-for-tenants).

    `CatalogWorkspace.to_api()` (gooddata_sdk's high-level wrapper, used by
    `sdk.catalog_workspace.create_or_update()`) doesn't expose the `dataSource`
    workspace attribute in the installed SDK version (1.58.0), so this builds
    the request with the same underlying `gooddata_api_client` model classes
    the SDK itself uses internally and PUTs it directly.

    Args:
        host (str): GoodData host URL.
        token (str): GoodData API token.
        workspace_id (str): Workspace to bind (created if it doesn't exist yet).
        name (str): Workspace display name.
        data_source_id (str): ID of the (already existing) data source entity.
        schema_path (list[str]): Schema path within that data source, e.g. ["TENANT_A"].
        parent_id (str): Optional parent workspace ID (for child/tenant workspaces).
    """
    from gooddata_api_client.model.json_api_workspace_in import JsonApiWorkspaceIn
    from gooddata_api_client.model.json_api_workspace_in_attributes import JsonApiWorkspaceInAttributes
    from gooddata_api_client.model.json_api_workspace_in_attributes_data_source import (
        JsonApiWorkspaceInAttributesDataSource,
    )
    from gooddata_api_client.model.json_api_workspace_in_document import JsonApiWorkspaceInDocument
    from gooddata_api_client.model.json_api_workspace_in_relationships import JsonApiWorkspaceInRelationships
    from gooddata_api_client.model.json_api_workspace_automation_out_relationships_workspace import (
        JsonApiWorkspaceAutomationOutRelationshipsWorkspace,
    )
    from gooddata_api_client.model.json_api_workspace_to_one_linkage import JsonApiWorkspaceToOneLinkage

    kwargs = {}
    if parent_id:
        kwargs["relationships"] = JsonApiWorkspaceInRelationships(
            parent=JsonApiWorkspaceAutomationOutRelationshipsWorkspace(
                data=JsonApiWorkspaceToOneLinkage(id=parent_id, type="workspace")
            )
        )

    document = JsonApiWorkspaceInDocument(
        data=JsonApiWorkspaceIn(
            id=workspace_id,
            attributes=JsonApiWorkspaceInAttributes(
                name=name,
                data_source=JsonApiWorkspaceInAttributesDataSource(id=data_source_id, schema_path=list(schema_path)),
            ),
            **kwargs,
        )
    )

    response = requests.put(
        f"{host}/api/v1/entities/workspaces/{workspace_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.gooddata.api+json",
            "Accept": "application/vnd.gooddata.api+json",
        },
        # camel_case=True is required here: to_dict() defaults to python
        # snake_case keys (data_source/schema_path), which the REST API
        # rejects — only the JSON-aliased keys (dataSource/schemaPath) are valid.
        json=document.to_dict(camel_case=True),
    )
    if response.ok:
        print(f"✅ {workspace_id} bound to data source '{data_source_id}' (schema {'/'.join(schema_path)})")
    elif "exists in the current workspace" in response.text or "already exists" in response.text:
        print(f"✅ {workspace_id} data source binding already applied.")
    else:
        print(f"❌ Failed to set data source for {workspace_id}: {response.status_code}")
        print(response.text)


def wipe_workspaces_and_permissions(
        workspace_ids: list[str],
        host: str,
        token: str,
        sdk: classmethod
) -> None:
    """
    Delete a list of workspaces and their associated permissions.

    Args:
        workspace_ids (list[str]): List of workspace IDs to delete.
        host (str): GoodData Cloud host URL.
        token (str): API token for authorization.
        sdk (GoodDataSdk): Initialized GoodData SDK instance.
    """

    # Input validation
    if not isinstance(workspace_ids, list):
        raise ValueError("workspace_ids must be a list.")
    if not isinstance(host, str):
        raise ValueError("host must be a string.")
    if not isinstance(token, str):
        raise ValueError("token must be a string.")

    # Delete each workspace
    for workspace_id in workspace_ids:
        try:
            sdk.catalog_workspace.delete_workspace(workspace_id=workspace_id)
            print(f"✅ Deleted workspace: {workspace_id}")
        except ValueError as ve:
            print(f"❌ Error deleting workspace {workspace_id}: {ve}")


def visualize_workspace_hierarchy(sdk: classmethod) -> None:
    tree = Tree()
    tree.create_node("GoodData", "root")
    for workspace in sdk.catalog_workspace.list_workspaces():
        parent_id = workspace.parent_id if workspace.parent_id else "root"
        if tree.get_node(workspace.id):
            continue  # we already established the node
        elif tree.get_node(parent_id):
            tree.create_node(workspace.name, workspace.id, parent=parent_id)
        else:
            temp_root = sdk.catalog_workspace.get_workspace(parent_id)
            temp_parent_id = temp_root.parent_id if temp_root.parent_id else "root"
            tree.create_node(temp_root.name, temp_root.id, parent=temp_parent_id)
            tree.create_node(workspace.name, workspace.id, parent=parent_id)
    tree.show(line_type="ascii-em")


## ULTIMATE hack to read locally present env files
## specific to this file to read env files two folders up...

def read_env_file(file_name_append: str = "test"):
    return dotenv_values(Path(__file__).resolve().parents[1] / f".env.{file_name_append}")


if __name__ == "__main__":
    temp = read_env_file(file_name_append="trial")  # read file .env.test
    gooddata = LoadGoodDataSdk(temp["GOODDATA_HOST"], temp["GOODDATA_TOKEN"])

    print(gooddata.tree())  # .show(line_type="ascii-em")
    # gooddata.altug(of_type='group', level=0, id='view.access',
    #               ds_id='public-demo-database', ds_right='USE',
    #               ws_id='gooddata_prod', ws_right='VIEW', )
