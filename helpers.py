from requests import get, post, put
from time import time
import json
from typing import Optional, Dict, Any
from html import escape

def html_cytoscape(elements_json: str):
    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dependency Graph</title>

        <!-- Cytoscape Core -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.21.0/cytoscape.min.js"></script>

        <!-- Dagre for hierarchical layouts -->
        <script src="https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"></script>
        <script src="https://unpkg.com/cytoscape-dagre@3.0.0/cytoscape-dagre.js"></script>

        <style>
            html,
            body {{
                margin: 0;
                padding: 0;
                background: #d6d9df;
                color: #111827;
                font-family: Avenir, "Helvetica Neue", Arial, sans-serif;
            }}
            #cy {{
                width: 100%;
                height: 600px;
                border: 1px solid #9ca3af;
                border-radius: 8px;
                background:
                    radial-gradient(circle at 1px 1px, rgba(17, 24, 39, 0.12) 1px, transparent 0),
                    linear-gradient(180deg, #e5e7eb 0%, #cbd5e1 100%);
                background-size: 24px 24px, 100% 100%;
                box-sizing: border-box;
            }}
            .tooltip {{
                position: absolute;
                z-index: 1000;
                max-width: 360px;
                background: rgba(17, 24, 39, 0.96);
                color: #f9fafb;
                padding: 10px 12px;
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 8px;
                font-size: 13px;
                line-height: 1.35;
                box-shadow: 0 18px 45px rgba(15, 23, 42, 0.28);
                display: none;
                pointer-events: none;
            }}
            .tooltip ul {{
                margin: 6px 0 0;
                padding-left: 18px;
            }}
        </style>
    </head>
    <body>

    <!--<h3>Optimized Dependency Graph</h3>-->
    <div id="cy"></div>
    <div class="tooltip" id="tooltip"></div>

    <script>
        console.log("Checking script loads...");

        document.addEventListener("DOMContentLoaded", function() {{
            console.log("Cytoscape:", typeof cytoscape !== 'undefined' ? "Loaded" : "NOT Loaded");
            console.log("Dagre:", typeof dagre !== 'undefined' ? "Loaded" : "NOT Loaded");
            console.log("cytoscape-dagre:", typeof window.cytoscapeDagre === 'function' ? "Loaded" : "Not exposed as global");

            if (typeof cytoscape === 'undefined') {{
                console.error("ERROR: Cytoscape did not load properly.");
                return;
            }}

            function getGraphLayout() {{
                const dagreLayout = {{
                    name: 'dagre',
                    rankDir: 'TB',
                    nodeSep: 50,
                    edgeSep: 20,
                    rankSep: 75
                }};

                if (typeof window.cytoscapeDagre === 'function') {{
                    try {{
                        console.log("Registering cytoscape-dagre...");
                        cytoscape.use(window.cytoscapeDagre);
                        return dagreLayout;
                    }} catch (error) {{
                        if (!String(error?.message || error).toLowerCase().includes('already')) {{
                            console.warn("cytoscape-dagre registration failed; checking whether layout is already available.", error);
                        }}
                    }}
                }}

                try {{
                    const testCy = cytoscape({{ headless: true, elements: [] }});
                    testCy.layout(dagreLayout).run();
                    testCy.destroy();
                    return dagreLayout;
                }} catch (error) {{
                    console.warn("cytoscape-dagre is unavailable; using built-in breadthfirst layout.", error);
                    return {{
                        name: 'breadthfirst',
                        directed: true,
                        padding: 50,
                        spacingFactor: 1.2
                    }};
                }}
            }}

            const elements = {elements_json};
            const graphLayout = getGraphLayout();

            var cy = cytoscape({{
                container: document.getElementById('cy'),
                elements: elements,
                style: [
                    {{
                        selector: 'node',
                        style: {{
                            'label': 'data(label)',
                            'text-halign': 'center',
                            'text-valign': 'bottom',
                            'text-margin-y': 9,
                            'color': '#ffffff',
                            'font-size': '12px',
                            'font-weight': 700,
                            'font-family': 'Avenir, Helvetica Neue, Arial, sans-serif',
                            'text-wrap': 'wrap',
                            'text-max-width': 150,
                            'text-background-color': '#111827',
                            'text-background-opacity': 0.94,
                            'text-background-padding': 4,
                            'text-background-shape': 'roundrectangle',
                            'width': 58,
                            'height': 58,
                            'shape': 'round-rectangle',
                            'background-color': '#64748b',
                            'border-width': 3,
                            'border-color': '#111827',
                            'shadow-blur': 12,
                            'shadow-color': 'rgba(15, 23, 42, 0.32)',
                            'shadow-offset-x': 0,
                            'shadow-offset-y': 3,
                            'shadow-opacity': 0.85
                        }}
                    }},
                    {{
                        selector: 'node[type="dataset"]',
                        style: {{
                            'background-color': '#0f766e',
                            'shape': 'round-rectangle'
                        }}
                    }},
                    {{
                        selector: 'node[type="attribute"]',
                        style: {{
                            'background-color': '#2563eb',
                            'shape': 'ellipse'
                        }}
                    }},
                    {{
                        selector: 'node[type="fact"], node[type="metric"]',
                        style: {{
                            'background-color': '#f97316',
                            'shape': 'diamond'
                        }}
                    }},
                    {{
                        selector: 'node[type="visualizationObject"]',
                        style: {{
                            'background-color': '#7c3aed',
                            'shape': 'round-rectangle',
                            'width': 102,
                            'height': 102
                        }}
                    }},
                    {{
                        selector: 'node[type="analyticalDashboard"]',
                        style: {{
                            'background-color': '#0891b2',
                            'shape': 'hexagon',
                            'width': 102,
                            'height': 102
                        }}
                    }},
                    {{
                        selector: 'node:selected',
                        style: {{
                            'border-color': '#facc15',
                            'border-width': 5
                        }}
                    }},
                    {{
                        selector: 'edge',
                        style: {{
                            'width': 2.5,
                            'line-color': '#111827',
                            'target-arrow-color': '#111827',
                            'target-arrow-shape': 'triangle',
                            'curve-style': 'bezier',
                            'opacity': 0.78
                        }}
                    }},
                    {{
                        selector: 'edge:selected',
                        style: {{
                            'line-color': '#facc15',
                            'target-arrow-color': '#facc15',
                            'width': 4,
                            'opacity': 1
                        }}
                    }}
                ],
                layout: graphLayout
            }});

            console.log("✅ Graph initialized successfully!");

            // Tooltip on Hover
            const tooltip = document.getElementById('tooltip');

            cy.on('mouseover', 'node', function(evt) {{
                var node = evt.target;
                var connectedNodes = [];

                // Get connected edges and extract nodes
                node.connectedEdges().forEach(function(edge) {{
                    let source = edge.source();
                    let target = edge.target();
                    if (source.id() !== node.id()) {{
                        connectedNodes.push(source);
                    }} else if (target.id() !== node.id()) {{
                        connectedNodes.push(target);
                    }}
                }});

                // Build the tooltip content
                let connectedInfo = connectedNodes.map(n => `<li>${{n.data('label')}} (${{n.data('type')}})</li>`).join("");

                tooltip.innerHTML = `<b>${{node.data('label')}}</b><br>
                                     <i>Type:</i> ${{node.data('type')}}<br>
                                     <i>Connected to:</i><ul>${{connectedInfo || '<li>None</li>'}}</ul>`;

                tooltip.style.display = 'block';
                tooltip.style.left = `${{evt.renderedPosition.x + 10}}px`;
                tooltip.style.top = `${{evt.renderedPosition.y + 10}}px`;
            }});

            cy.on('mouseout', 'node', function(evt) {{
                tooltip.style.display = 'none';
            }});
        }});
    </script>

    </body>
    </html>
    """
    return html_code

def html_embedded_dashboard(host: str, workspace_id: str, dashboard_id: str, token: str, height: int = 700, show_navigation: bool = False):
    """Generate HTML for embedded GoodData dashboard with token authentication via postMessage."""
    html_code = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                margin: 0;
                padding: 0;
                overflow: hidden;
            }}
            #embedded-dashboard {{
                width: 100%;
                height: {height}px;
                border: none;
            }}
        </style>
    </head>
    <body>
        <iframe
            id="embedded-dashboard"
            src="{host}dashboards/embedded/#/workspace/{workspace_id}/dashboard/{dashboard_id}?apiTokenAuthentication=true&showNavigation={'true' if show_navigation else 'false'}&setHeight={height}"
            frameborder="0">
        </iframe>
        <script>
            console.log("Setting up embedded dashboard with token authentication");

            // Function to send postMessage to iframe
            function sendMessageToIframe(message) {{
                const iframe = document.getElementById("embedded-dashboard");
                if (iframe && iframe.contentWindow) {{
                    const origin = "*";
                    iframe.contentWindow.postMessage(message, origin);
                    console.log("Sending message to embedded dashboard", message);
                }}
            }}

            // Listen for token request from iframe
            window.addEventListener("message", function (e) {{
                // Log all messages for debugging
                console.log("Post message received", e.data);

                // Normalize event data - handle both formats (with and without gdc wrapper)
                const eventData = e.data.gdc || e.data;
                const eventName = eventData?.event?.name || eventData?.name;

                // Handle API token request
                if (eventName == "listeningForApiToken") {{
                    const postMessageStructure = {{
                        gdc: {{
                            product: "dashboard",
                            event: {{
                                name: "setApiToken",
                                data: {{
                                    token: "{token}"
                                }}
                            }}
                        }}
                    }};
                    sendMessageToIframe(postMessageStructure);
                    console.log("Token sent to embedded dashboard");
                }}
            }}, false);
        </script>
    </body>
    </html>
    """
    return html_code


def html_gooddata_ui_dashboard(host: str, workspace_id: str, dashboard_id: str, token: str, height: int = 700):
    """Render a GoodData.UI dashboard web component without an iframe.

    GoodData serves the web-component bundle from the workspace endpoint. The
    bundle uses React internally and authenticates through the token provider.
    The hosting GoodData instance must allow the Streamlit origin via CORS.
    """
    host = host.rstrip("/")
    workspace_json = json.dumps(str(workspace_id))
    dashboard_attr = escape(str(dashboard_id), quote=True)
    workspace_attr = escape(str(workspace_id), quote=True)
    token_json = json.dumps(str(token))
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            html, body, gd-dashboard-embed {{
                margin: 0;
                width: 100%;
                min-height: {height}px;
            }}
            body {{ overflow: auto; }}
        </style>
        <script type="module">
            import {{ setContext }} from "{host}/components/{workspace_attr}.js";
            import factory, {{ TigerTokenAuthProvider }} from "{host}/components/tigerBackend.js";

            setContext({{
                backend: factory()
                    .onHostname({json.dumps(host)})
                    .withAuthentication(new TigerTokenAuthProvider({token_json})),
                workspaceId: {workspace_json},
            }});
        </script>
    </head>
    <body>
        <gd-dashboard-embed
            dashboard="{dashboard_attr}"
            workspace="{workspace_attr}"
            readonly>
        </gd-dashboard-embed>
    </body>
    </html>
    """

def time_it(ref_time: float=0, run: bool = False):
    """
    2-step function hack
    Get current time in first run and difference in the second one
    :type ref_time: date time stamp from previous run (float value)
    :param run: indicator that will trigger difference computation
    """
    # TO-DO: case run = True and no ref_time submit, how to cope with that
    if not run:
        return time()
    else:
        return time() - ref_time


def display_value(value):
    if value in (None, "", [], {}):
        return "N/A"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "N/A"
    if isinstance(value, dict):
        for key in ("name", "id", "identifier", "title", "value"):
            if value.get(key):
                return str(value[key])
        return str(value)
    return str(value)


def pick_nested_value(data, *paths):
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


def flatten_recipients(attrs):
    raw = pick_nested_value(
        attrs,
        ("recipients",),
        ("email", "recipients"),
        ("notification", "recipients"),
        ("alert", "recipients"),
        ("schedule", "recipients"),
    )
    if isinstance(raw, list):
        items = []
        for item in raw:
            if isinstance(item, dict):
                items.append(
                    str(
                        item.get("email")
                        or item.get("id")
                        or item.get("name")
                        or item.get("identifier")
                        or item
                    )
                )
            else:
                items.append(str(item))
        return ", ".join(items) if items else "N/A"
    return display_value(raw)


def automation_rows(items, table_kind="schedule", include_filter_context=False):
    rows = []
    for item in items:
        attrs = item.get("attributes", {}) if isinstance(item, dict) else {}
        base = {
            "ID": item.get("id", "N/A") if isinstance(item, dict) else "N/A",
            "Name": display_value(
                pick_nested_value(attrs, ("name",), ("title",), ("metadata", "name"))
            ),
            "Type": display_value(
                pick_nested_value(attrs, ("type",), ("kind",), ("automationType",))
            ),
            "Enabled": display_value(
                pick_nested_value(attrs, ("enabled",), ("active",), ("isEnabled",))
            ),
            "Recipients": flatten_recipients(attrs),
        }
        if include_filter_context:
            base["Filter Context"] = display_value(
                pick_nested_value(
                    attrs,
                    ("filterContext", "id"),
                    ("filterContext", "identifier"),
                    ("filterContextId",),
                    ("execution", "filterContext", "id"),
                )
            )
        if table_kind == "alert":
            base["Threshold"] = display_value(
                pick_nested_value(
                    attrs,
                    ("threshold",),
                    ("condition", "threshold"),
                    ("alert", "threshold"),
                    ("trigger", "threshold"),
                )
            )
        else:
            base["Cron"] = display_value(
                pick_nested_value(
                    attrs,
                    ("cron",),
                    ("schedule", "cron"),
                    ("recurrence", "cron"),
                    ("timezoneCron",),
                )
            )
        rows.append(base)
    return rows


def notification_channel_rows(channels):
    rows = []
    for ch in channels:
        data = ch.to_dict() if hasattr(ch, "to_dict") else (ch if isinstance(ch, dict) else {})
        attrs = data.get("attributes", data) if isinstance(data, dict) else {}
        if not isinstance(attrs, dict):
            attrs = {}
        rows.append({
            "ID": data.get("id", getattr(ch, "id", "N/A")),
            "Name": display_value(pick_nested_value(attrs, ("name",), ("title",))),
            "Type": display_value(pick_nested_value(attrs, ("type",), ("kind",))),
            "Webhook URL": display_value(
                pick_nested_value(
                    attrs,
                    ("url",),
                    ("webhook_url",),
                    ("webhookUrl",),
                    ("destination", "url"),
                )
            ),
        })
    return rows


def pretty_json(value, fallback=None):
    data = value if value else fallback
    return json.dumps(data, indent=2, default=str)


def workspace_overview_stats(semantics):
    dashboards = semantics.get("dashboards", []) or []
    visualizations = semantics.get("visualizations", []) or []
    metrics = semantics.get("metrics", []) or []
    filter_contexts = semantics.get("filter_contexts", []) or []
    dependency_nodes = semantics.get("dependencies", {}).get("nodes", []) or []
    dependency_edges = semantics.get("dependencies", {}).get("edges", []) or []
    dashboard_shares = semantics.get("dashboard_shares", {}) or {}

    afm_measures = 0
    afm_attributes = 0
    afm_filters = 0
    for visualization in visualizations:
        afm = visualization.get("afm", {}) or {}
        afm_measures += len(afm.get("measures", []) or [])
        afm_attributes += len(afm.get("attributes", []) or [])
        afm_filters += len(afm.get("filters", []) or [])

    share_assignments = sum(len(items or []) for items in dashboard_shares.values())

    return {
        "dashboards": len(dashboards),
        "visualizations": len(visualizations),
        "metrics": len(metrics),
        "filter_contexts": len(filter_contexts),
        "afm_measures": afm_measures,
        "afm_attributes": afm_attributes,
        "afm_filters": afm_filters,
        "dependency_nodes": len(dependency_nodes),
        "dependency_edges": len(dependency_edges),
        "dashboard_shares": share_assignments,
    }


def _extract_filter_context_ref_id(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None

    ref_id = value.get("id")
    if isinstance(ref_id, str):
        return ref_id

    identifier = value.get("identifier")
    if isinstance(identifier, str):
        return identifier
    if isinstance(identifier, dict):
        nested_id = identifier.get("id") or identifier.get("identifier")
        if isinstance(nested_id, str):
            return nested_id

    data = value.get("data")
    if isinstance(data, dict):
        data_id = data.get("id") or data.get("identifier")
        if isinstance(data_id, str):
            return data_id

    return None


def _collect_filter_context_ids_and_filters(node):
    referenced_filter_context_ids = set()
    direct_filters = []

    def walk(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                key_lower = str(key).lower()
                if key_lower in {"filters", "filter"} and isinstance(nested, list):
                    direct_filters.extend(nested)
                if "filtercontext" in key_lower:
                    ref_id = _extract_filter_context_ref_id(nested)
                    if ref_id:
                        referenced_filter_context_ids.add(ref_id)
                walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(node)
    return referenced_filter_context_ids, direct_filters


def dashboard_effective_filter_stats(semantics, dashboard_id):
    dashboards = semantics.get("dashboards", []) or []
    filter_contexts = semantics.get("filter_contexts", []) or []
    dashboard = next((item for item in dashboards if item.get("id") == dashboard_id), None)
    if not dashboard:
        return {
            "filter_context_objects": 0,
            "effective_filters": 0,
        }

    filter_context_by_id = {
        item.get("id"): item for item in filter_contexts if item.get("id")
    }
    referenced_filter_context_ids, direct_filters = _collect_filter_context_ids_and_filters(
        dashboard.get("raw", {})
    )

    referenced_filter_count = 0
    for filter_context_id in referenced_filter_context_ids:
        filter_context = filter_context_by_id.get(filter_context_id)
        if filter_context:
            referenced_filter_count += len(filter_context.get("filters", []) or [])

    return {
        "filter_context_objects": len(referenced_filter_context_ids),
        "effective_filters": referenced_filter_count + len(direct_filters),
    }


def dashboard_filter_context_records(semantics, dashboard_id):
    dashboards = semantics.get("dashboards", []) or []
    filter_contexts = semantics.get("filter_contexts", []) or []
    dashboard = next((item for item in dashboards if item.get("id") == dashboard_id), None)
    if not dashboard:
        return filter_contexts

    filter_context_by_id = {
        item.get("id"): item for item in filter_contexts if item.get("id")
    }
    referenced_filter_context_ids, _ = _collect_filter_context_ids_and_filters(
        dashboard.get("raw", {})
    )

    if not referenced_filter_context_ids:
        return filter_contexts

    return [
        filter_context_by_id[filter_context_id]
        for filter_context_id in referenced_filter_context_ids
        if filter_context_id in filter_context_by_id
    ]

# Helper for LDM preparation (stub)
def csv_to_ldm_request(uploaded_file):
    import pandas as pd
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file, nrows=1)  # Just to get columns
        fields = list(df.columns)
        # Placeholder: generate a dict/request with these fields for LDM
        return f"LDM request would be generated for fields: {fields}"
    return "No file uploaded."


def load_restore_profiles() -> Dict[str, Any]:
    """Load restore profiles from JSON file"""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

    profiles_file = Path(__file__).resolve().parents[1] / "restore_profiles.json"

    if profiles_file.exists():
        try:
            import json
            with open(profiles_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            return {"profiles": [], "error": str(e)}
    else:
        # Return default structure
        return {"profiles": []}


def save_restore_profiles(profiles_data: Dict[str, Any]) -> bool:
    """Save restore profiles to JSON file"""
    import sys
    from pathlib import Path
    import json
    sys.path.append(str(Path(__file__).resolve().parents[1]))

    profiles_file = Path(__file__).resolve().parents[1] / "restore_profiles.json"

    try:
        with open(profiles_file, 'w') as f:
            json.dump(profiles_data, f, indent=2)
        return True
    except Exception as e:
        return False


def load_users_internal() -> Dict[str, Any]:
    """Load internal users from JSON file"""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

    users_file = Path(__file__).resolve().parents[1] / "restore_SEE_users.json"

    if users_file.exists():
        try:
            import json
            with open(users_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            return {"users": [], "userGroups": [], "error": str(e)}
    else:
        return {"users": [], "userGroups": []}


def load_users_testing_template() -> Dict[str, Any]:
    """Load testing users template from JSON file"""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

    template_file = Path(__file__).resolve().parents[1] / "restore_test_users_template.json"

    if template_file.exists():
        try:
            import json
            with open(template_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            return {"users": [], "userGroups": [], "error": str(e)}
    else:
        # Return default template structure if template file doesn't exist
        return {
            "userGroups": [
                {
                    "id": "test_group",
                    "name": "Test Group",
                    "permissions": []
                }
            ],
            "users": [
                {
                    "id": "test.user",
                    "firstname": "Test",
                    "lastname": "User",
                    "email": "test.user@example.com",
                    "permissions": [],
                    "settings": [],
                    "userGroups": [
                        {
                            "id": "test_group",
                            "type": "userGroup"
                        }
                    ],
                    "workspace_assignments": []
                }
            ]
        }


def load_users_testing() -> Dict[str, Any]:
    """Load testing users configuration from JSON file"""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1]))

    users_file = Path(__file__).resolve().parents[1] / "restore_test_users.json"

    if users_file.exists():
        try:
            import json
            with open(users_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            return {"users": [], "userGroups": [], "error": str(e)}
    else:
        # Return empty structure if file doesn't exist
        return {"users": [], "userGroups": []}


def save_users_testing(users_data: Dict[str, Any]) -> bool:
    """Save testing users configuration to JSON file"""
    import sys
    from pathlib import Path
    import json
    sys.path.append(str(Path(__file__).resolve().parents[1]))

    users_file = Path(__file__).resolve().parents[1] / "restore_test_users.json"

    try:
        with open(users_file, 'w') as f:
            json.dump(users_data, f, indent=2)
        return True
    except Exception as e:
        return False


def load_plugin_list() -> Dict[str, Any]:
    """Load dashboard plugin registry from JSON file."""
    from pathlib import Path
    import json
    plugins_file = Path(__file__).resolve().parents[2] / "frontend" / "plugins" / "DB_Plugin_list.json"
    if plugins_file.exists():
        try:
            with open(plugins_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            return {"plugins": [], "error": str(e)}
    return {"plugins": []}


def save_plugin_list(data: Dict[str, Any]) -> bool:
    """Save dashboard plugin registry to JSON file."""
    from pathlib import Path
    import json
    plugins_file = Path(__file__).resolve().parents[2] / "frontend" / "plugins" / "DB_Plugin_list.json"
    try:
        with open(plugins_file, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def discover_plugins_from_s3(env_vars: dict, region: str = 'us-east-2') -> Dict[str, Any]:
    """Delegate S3 discovery to structure_builder.plugins.discover_plugin_list_from_s3."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from backend.structure_builder.plugins import discover_plugin_list_from_s3
    return discover_plugin_list_from_s3(env_vars, region=region)


def list_workspace_plugins(host: str, token: str, workspace_id: str) -> list:
    """Return dashboard plugins currently registered in a workspace."""
    url = f"{host.rstrip('/')}/api/v1/entities/workspaces/{workspace_id}/dashboardPlugins"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.gooddata.api+json"}
    try:
        response = get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception:
        pass
    return []


def register_plugin_with_workspace(host: str, token: str, workspace_id: str, plugin: dict) -> dict:
    """
    Register or update a dashboard plugin in a workspace via the entities API.
    Checks existence first: POST to create, PUT to update.
    """
    base = f"{host.rstrip('/')}/api/v1/entities/workspaces/{workspace_id}/dashboardPlugins"
    auth = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.gooddata.api+json"}
    api  = {**auth, "Content-Type": "application/vnd.gooddata.api+json"}

    payload = {"data": {
        "type": "dashboardPlugin",
        "id": plugin["id"],
        "attributes": {
            "name": plugin.get("name", plugin["id"]),
            "url": plugin["url"],
        },
    }}

    exists = get(f"{base}/{plugin['id']}", headers=auth).status_code == 200
    if exists:
        response = put(f"{base}/{plugin['id']}", headers=api, json=payload)
        action = "updated"
    else:
        response = post(base, headers=api, json=payload)
        action = "registered"

    if response.status_code in [200, 201, 204]:
        return {"success": True, "action": action, "id": plugin["id"]}

    try:
        detail = response.json()
    except Exception:
        detail = response.text
    return {"success": False, "error": f"HTTP {response.status_code}: {detail}", "id": plugin["id"]}


def write_plugin_yaml_helper(plugin: dict) -> str:
    """Write plugin YAML to analytics/plugins/ and return the written path string."""
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from backend.structure_builder.plugins import write_plugin_yaml
    path = write_plugin_yaml(plugin)
    return str(path)


def restore_from_url(
    gd_sdk,
    host: str,
    token: str,
    workspace_id: Optional[str] = None,
    datasource_id: Optional[str] = None,
    ldm_url: Optional[str] = None,
    workspace_analytics_url: Optional[str] = None,
    workspace_data_filters_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Restore GoodData workspace from JSON files using Python SDK.

    Args:
        gd_sdk: LoadGoodDataSdk instance (from common.py)
        workspace_id: Target workspace ID to restore to (required if not supplied by the caller)
        datasource_id: Data source ID to update references in LDM (optional)
        ldm_url: URL to fetch logical data model JSON from (required)
        workspace_analytics_url: URL to fetch workspace analytics JSON from (required)

    Returns:
        Dictionary with restore status, detailed report, and statistics
    """
    from gooddata_sdk import CatalogWorkspace
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1]))  # Add backend/ to path

    results = {
        "success": True,
        "errors": [],
        "warnings": [],
        "steps": [],
        "statistics": {
            "workspace_created": False,
            "workspace_updated": False,
            "wdf_created": 0,
            "wdf_updated": 0,
            "ldm_updated": False,
            "analytics_updated": False
        },
        "report": []
    }

    if not workspace_id:
        results["errors"].append("Workspace ID is required; enter it in the restore form")
        results["success"] = False
        return results

    if not ldm_url:
        results["errors"].append("LDM URL is required")
        results["success"] = False
        return results

    if not workspace_analytics_url:
        results["errors"].append("Workspace Analytics URL is required")
        results["success"] = False
        return results

    def fetch_json(url: str) -> Optional[Dict]:
        """Fetch JSON from URL"""
        try:
            response = get(url, headers={"Accept": "application/json"}, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"Failed to fetch {url}: HTTP {response.status_code}"
                results["errors"].append(error_msg)
                results["report"].append(f"❌ {error_msg}")
                return None
        except Exception as e:
            error_msg = f"Error fetching {url}: {str(e)}"
            results["errors"].append(error_msg)
            results["report"].append(f"❌ {error_msg}")
            return None

    def update_datasource_refs_in_ldm(ldm_dict: Dict, target_ds_id: str) -> None:
        """Recursively update dataSourceId references in LDM dictionary"""
        if isinstance(ldm_dict, dict):
            # Update dataSourceTableId.dataSourceId references
            if "dataSourceTableId" in ldm_dict and isinstance(ldm_dict["dataSourceTableId"], dict):
                if "dataSourceId" in ldm_dict["dataSourceTableId"]:
                    old_id = ldm_dict["dataSourceTableId"]["dataSourceId"]
                    ldm_dict["dataSourceTableId"]["dataSourceId"] = target_ds_id
                    if old_id != target_ds_id:
                        results["report"].append(f"  ↳ Updated dataSourceId: {old_id} → {target_ds_id}")
            # Also check for direct dataSourceId fields
            if "dataSourceId" in ldm_dict and ldm_dict.get("dataSourceId"):
                old_id = ldm_dict["dataSourceId"]
                ldm_dict["dataSourceId"] = target_ds_id
                if old_id != target_ds_id:
                    results["report"].append(f"  ↳ Updated dataSourceId: {old_id} → {target_ds_id}")
            # Recursively process all values
            for value in ldm_dict.values():
                update_datasource_refs_in_ldm(value, target_ds_id)
        elif isinstance(ldm_dict, list):
            for item in ldm_dict:
                update_datasource_refs_in_ldm(item, target_ds_id)

    # ============================================
    # Handle Workspace Restoration
    # ============================================
    results["workspace_id_used"] = workspace_id  # Store for debugging
    results["report"].append(f"\n🏢 **Workspace Restoration**")
    results["report"].append(f"Target Workspace ID: `{workspace_id}`")
    if datasource_id:
        results["report"].append(f"Data Source ID (for LDM references): `{datasource_id}`")

    try:
        # Check if workspace exists
        try:
            existing_ws = gd_sdk._sdk.catalog_workspace.get_workspace(workspace_id)
            ws_exists = True
            ws_name = existing_ws.name
            results["report"].append(f"✓ Workspace exists: `{ws_name}`, will update")
        except Exception:
            ws_exists = False
            results["report"].append(f"✓ Workspace does not exist, will create")

        # Create or update workspace using SDK
        try:
            # Get workspace name from ID
            ws_name = workspace_id.replace("_", " ").replace("-", " ").title()
            workspace = CatalogWorkspace(workspace_id=workspace_id, name=ws_name)
            gd_sdk._sdk.catalog_workspace.create_or_update(workspace)

            action = "Updated" if ws_exists else "Created"
            results["steps"].append(f"{action} workspace: {workspace_id}")
            results["statistics"][f"workspace_{'updated' if ws_exists else 'created'}"] = True
            results["report"].append(f"✅ {action} workspace: `{workspace_id}`")
        except Exception as e:
            error_msg = f"Failed to {('update' if ws_exists else 'create')} workspace: {str(e)}"
            results["errors"].append(error_msg)
            results["report"].append(f"❌ {error_msg}")
            results["success"] = False

        # Create/Update Workspace Data Filters (must be done before LDM)
        if results["success"] and workspace_data_filters_url:
            results["report"].append(f"\n🔍 **Workspace Data Filters**")
            results["report"].append(f"📥 Fetching WDF from: {workspace_data_filters_url}")
            wdf_data = fetch_json(workspace_data_filters_url)
            if wdf_data:
                # Handle different JSON structures
                if "workspaceDataFilters" in wdf_data:
                    wdf_list = wdf_data["workspaceDataFilters"]
                elif isinstance(wdf_data, list):
                    wdf_list = wdf_data
                else:
                    wdf_list = [wdf_data]

                for wdf_item in wdf_list:
                    # Extract the data object
                    wdf_payload = wdf_item.get("data", wdf_item) if isinstance(wdf_item, dict) else wdf_item

                    if not isinstance(wdf_payload, dict) or "id" not in wdf_payload:
                        results["warnings"].append(f"Skipping invalid WDF item: {wdf_item}")
                        continue

                    wdf_id = wdf_payload["id"]
                    results["report"].append(f"  Processing WDF: `{wdf_id}`")

                    # Check if WDF exists
                    check_url = f"{host}/api/v1/entities/workspaces/{workspace_id}/workspaceDataFilters/{wdf_id}"
                    check_headers = {
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.gooddata.api+json"
                    }
                    try:
                        check_response = get(check_url, headers=check_headers)
                        wdf_exists = check_response.status_code == 200
                    except Exception:
                        wdf_exists = False

                    # Create or update WDF
                    if wdf_exists:
                        # Update existing WDF
                        update_url = f"{host}/api/v1/entities/workspaces/{workspace_id}/workspaceDataFilters/{wdf_id}"
                        update_headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/vnd.gooddata.api+json",
                            "Accept": "application/vnd.gooddata.api+json"
                        }
                        try:
                            response = put(update_url, headers=update_headers, json={"data": wdf_payload})
                            if response.status_code in [200, 201, 204]:
                                results["statistics"]["wdf_updated"] += 1
                                results["report"].append(f"    ✅ Updated WDF: `{wdf_id}`")
                            else:
                                results["errors"].append(f"Failed to update WDF {wdf_id}: HTTP {response.status_code}")
                                results["report"].append(f"    ❌ Failed to update WDF: `{wdf_id}`")
                        except Exception as e:
                            results["errors"].append(f"Error updating WDF {wdf_id}: {str(e)}")
                            results["report"].append(f"    ❌ Error updating WDF: `{wdf_id}`")
                    else:
                        # Create new WDF
                        create_url = f"{host}/api/v1/entities/workspaces/{workspace_id}/workspaceDataFilters"
                        create_headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/vnd.gooddata.api+json",
                            "Accept": "application/vnd.gooddata.api+json"
                        }
                        try:
                            response = post(create_url, headers=create_headers, json={"data": wdf_payload})
                            if response.status_code in [200, 201, 204]:
                                results["statistics"]["wdf_created"] += 1
                                results["report"].append(f"    ✅ Created WDF: `{wdf_id}`")
                            else:
                                # Check if it's an "already exists" error
                                try:
                                    error_detail = response.json().get("detail", "")
                                    if "already exists" in error_detail.lower() or "already stored" in error_detail.lower():
                                        results["statistics"]["wdf_updated"] += 1
                                        results["report"].append(f"    ✅ WDF already exists: `{wdf_id}`")
                                    else:
                                        results["errors"].append(f"Failed to create WDF {wdf_id}: HTTP {response.status_code} - {error_detail}")
                                        results["report"].append(f"    ❌ Failed to create WDF: `{wdf_id}`")
                                except Exception:
                                    results["errors"].append(f"Failed to create WDF {wdf_id}: HTTP {response.status_code}")
                                    results["report"].append(f"    ❌ Failed to create WDF: `{wdf_id}`")
                        except Exception as e:
                            results["errors"].append(f"Error creating WDF {wdf_id}: {str(e)}")
                            results["report"].append(f"    ❌ Error creating WDF: `{wdf_id}`")
            else:
                warning = "Workspace data filters URL provided but data could not be fetched"
                results["warnings"].append(warning)
                results["report"].append(f"⚠️ {warning}")

        # Update LDM
        if results["success"]:
            results["report"].append(f"📥 Fetching LDM from: {ldm_url}")
            ldm_data = fetch_json(ldm_url)
            if ldm_data:
                # Transform LDM structure to match API expectations
                # API expects: {"ldm": {...}}
                # GitHub might have: {"layout": {"ldm": {...}}} or just {"ldm": {...}}
                if "layout" in ldm_data and "ldm" in ldm_data["layout"]:
                    # Extract from layout.ldm
                    ldm_payload = {"ldm": ldm_data["layout"]["ldm"]}
                    results["report"].append(f"  ↳ Extracted LDM from layout.ldm structure")
                elif "ldm" in ldm_data:
                    # Already has ldm at root
                    ldm_payload = {"ldm": ldm_data["ldm"]}
                    results["report"].append(f"  ↳ Using LDM from root structure")
                else:
                    # Assume the whole thing is the LDM
                    ldm_payload = {"ldm": ldm_data}
                    results["report"].append(f"  ↳ Wrapping entire JSON as LDM")

                # Update data source IDs in LDM if datasource_id is provided
                if datasource_id:
                    results["report"].append(f"  🔄 Updating data source references to: `{datasource_id}`")
                    update_datasource_refs_in_ldm(ldm_payload, datasource_id)

                try:
                    # Use API directly with JSON (SDK expects objects, not dicts from URLs)
                    url = f"{host}/api/v1/layout/workspaces/{workspace_id}/logicalModel"
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    response = put(url, headers=headers, json=ldm_payload)
                    if response.status_code not in [200, 204]:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")

                    results["steps"].append(f"Updated LDM for workspace: {workspace_id}")
                    results["statistics"]["ldm_updated"] = True
                    results["report"].append(f"✅ Updated LDM for workspace: `{workspace_id}`")
                except Exception as e:
                    error_msg = f"Failed to update LDM: {str(e)}"
                    results["errors"].append(error_msg)
                    results["report"].append(f"❌ {error_msg}")
                    results["success"] = False
            else:
                error_msg = "LDM data could not be fetched"
                results["errors"].append(error_msg)
                results["report"].append(f"❌ {error_msg}")
                results["success"] = False

        # Update Analytics Model
        if results["success"]:
            results["report"].append(f"📥 Fetching Analytics Model from: {workspace_analytics_url}")
            analytics_data = fetch_json(workspace_analytics_url)
            if analytics_data:
                # Transform Analytics structure to match API expectations
                # API expects: {"analytics": {...}}
                # GitHub might have: {"layout": {"analytics": {...}}} or just {"analytics": {...}}
                if "layout" in analytics_data and "analytics" in analytics_data["layout"]:
                    # Extract from layout.analytics
                    analytics_payload = {"analytics": analytics_data["layout"]["analytics"]}
                    results["report"].append(f"  ↳ Extracted analytics from layout.analytics structure")
                elif "analytics" in analytics_data:
                    # Already has analytics at root
                    analytics_payload = {"analytics": analytics_data["analytics"]}
                    results["report"].append(f"  ↳ Using analytics from root structure")
                else:
                    # Assume the whole thing is the analytics
                    analytics_payload = {"analytics": analytics_data}
                    results["report"].append(f"  ↳ Wrapping entire JSON as analytics")

                try:
                    # Use API directly with JSON (SDK expects objects, not dicts from URLs)
                    url = f"{host}/api/v1/layout/workspaces/{workspace_id}/analyticsModel"
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    response = put(url, headers=headers, json=analytics_payload)
                    if response.status_code not in [200, 204]:
                        raise Exception(f"HTTP {response.status_code}: {response.text}")

                    results["steps"].append(f"Updated analytics model for workspace: {workspace_id}")
                    results["statistics"]["analytics_updated"] = True
                    results["report"].append(f"✅ Updated analytics model for workspace: `{workspace_id}`")
                except Exception as e:
                    error_msg = f"Failed to update analytics model: {str(e)}"
                    results["errors"].append(error_msg)
                    results["report"].append(f"❌ {error_msg}")
                    results["success"] = False
            else:
                error_msg = "Analytics model data could not be fetched"
                results["errors"].append(error_msg)
                results["report"].append(f"❌ {error_msg}")
                results["success"] = False
    except Exception as e:
        error_msg = f"Error processing workspace: {str(e)}"
        results["errors"].append(error_msg)
        results["report"].append(f"❌ {error_msg}")
        results["success"] = False

    # Generate summary
    results["report"].append(f"\n📊 **Restore Summary**")
    results["report"].append(f"- ✅ Steps completed: {len(results['steps'])}")
    results["report"].append(f"- ❌ Errors: {len(results['errors'])}")
    results["report"].append(f"- ⚠️ Warnings: {len(results['warnings'])}")
    results["report"].append(f"- {'✅ Restore completed successfully!' if results['success'] else '❌ Restore completed with errors'}")

    return results
