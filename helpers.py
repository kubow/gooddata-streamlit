from requests import exceptions, get, post, delete
from time import time
import json

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


def pretty_json(value, fallback=None):
    data = value if value else fallback
    return json.dumps(data, indent=2, default=str)


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

def demo_content():
    return {
        "GoodDemo": {
            "ds": "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/master/gooddemo/dataSource/dataSource.json",
            "ldm": "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/master/gooddemo/workspaces/demo/ldm.json",
            "ws": "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/master/gooddemo/workspaces/demo/workspaceAnalytics.json"
        },
        "Ecommerce": {
            "ds": "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/master/ecommerce-demo/dataSource/dataSource.json",
            "ldm": "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/master/ecommerce-demo/workspaces/demo/ldm.json",
            "ws": "https://raw.githubusercontent.com/gooddata/gooddata-public-demos/master/ecommerce-demo/workspaces/demo/workspaceAnalytics.json"
        },
    }

# Helper for LDM preparation (stub)
def csv_to_ldm_request(uploaded_file):
    import pandas as pd
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file, nrows=1)  # Just to get columns
        fields = list(df.columns)
        # Placeholder: generate a dict/request with these fields for LDM
        return f"LDM request would be generated for fields: {fields}"
    return "No file uploaded."


def reload_cache(hostname, token, data_source_id):
    url = f"{hostname}/api/v1/actions/dataSources/{data_source_id}/uploadNotification"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    return post(url, headers=headers)


def execute_api_call(hostname, token, workspace_id, data):
    url = f"{hostname}/api/v1/actions/workspaces/{workspace_id}/execution/afm/execute"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    return post(url, headers=headers, json=data)


def get_results(hostname, token, workspace_id, execution_result_id):
    url = f"{hostname}/api/v1/actions/workspaces/{workspace_id}/execution/afm/execute/result/{execution_result_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    return get(url, headers=headers)


def get_filter_contexts(hostname, token, workspace_id):
    """Fetch filter contexts via REST API (fallback when SDK fails)."""
    url = f"{hostname}/api/v1/entities/workspaces/{workspace_id}/filterContexts?size=200"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    return get(url, headers=headers, timeout=30)


def get_ldm_via_rest(hostname, token, workspace_id):
    """Fetch LDM via REST API (fallback when SDK fails)."""
    url = f"{hostname}/api/v1/layout/workspaces/{workspace_id}/ldm"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    return get(url, headers=headers, timeout=30)


def get_pdm_via_rest(hostname, token, workspace_id):
    """Fetch PDM via REST API (fallback when SDK fails)."""
    url = f"{hostname}/api/v1/layout/workspaces/{workspace_id}/pdm"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    return get(url, headers=headers, timeout=30)


def probe_url(url):
    """Probe if a URL is accessible (for dashboard embedding)."""
    try:
        r = get(url, timeout=5)
        return r.status_code < 400
    except Exception:
        return False


def process_ldm_rest_response(resp_data: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Process LDM REST API response and return (datasets_rows, columns_rows, refs_rows)."""
    datasets_rows: list[dict] = []
    columns_rows: list[dict] = []
    refs_rows: list[dict] = []
    try:
        ds_list = (resp_data.get("ldm") or {}).get("datasets", [])
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
    return datasets_rows, columns_rows, refs_rows


def process_pdm_rest_response(resp_data: dict) -> dict:
    """Process PDM REST API response and return table to data source mapping."""
    table_to_ds = {}
    try:
        tables = (resp_data.get("pdm") or {}).get("tables") or []
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
    return table_to_ds


def process_filter_contexts_rest_response(resp_data: dict, used_counts: dict = None) -> list[dict]:
    """Process filter contexts REST API response and return rows."""
    rows: list[dict] = []
    used_counts = used_counts or {}
    try:
        items = resp_data.get("data") or []
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
        pass
    return rows


def general_request(host: str, token: str, obj_id: str, req_type: str, ws_id: str) -> None:
    """
    This method is used when you want to wipe/delete workspaces via id and related workspace permissions
        :param host:
        :param token:
        :param obj_id: id of the datafilter, reachable via /api/v1/entities/workspaces/...
        :param req_type: one of below options... creates the logic
        :param ws_id: id of the datafilter, reachable via /api/v1/entities/workspaces/...
        :return:
    """
    req_types = {
        "org": {
            "adr": f"{host}/api/v1/entities/organization",
            "type": "get",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        },
        "org_alt": {
            "adr": f"{host}/api/v1/entities/organization?metaInclude=permissions",
            "type": "get",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        },
        "lic": {
            "adr": f"{host}/api/v1/actions/resolveEntitlements",
            "type": "get",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        },
        "loc": {
            "adr": f"{host}/api/v1/entities/organizationSettings",
            "type": "get",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        },
        "usr": {
            "adr": f"{host}/api/v1/entities/users",
            "type": "get",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        },
        "wks": {
            "adr": f"{host}",
            "type": "get",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        },
        "cache": {
            "adr": f"{host}/api/v1/actions/dataSources/{obj_id}/uploadNotification",
            "type": "post",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        },
        "afm": {
            "adr": f"{host}/api/v1/actions/workspaces/{ws_id}/execution/afm/execute",
            "type": "post",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json",  "Accept": "application/json"},
        },
        "res": {
            "adr": f"{host}/api/v1/actions/workspaces/{ws_id}/execution/afm/execute/result/{obj_id}",
            "type": "get",
            "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        },
    }

    if not isinstance(ws_id, str):
        raise ValueError("ws_id must be a string.")

    if not isinstance(obj_id, str):
        raise ValueError("obj_id must be a string.")

    if not isinstance(host, str):
        raise ValueError("host must be a string.")

    if not isinstance(token, str):
        raise ValueError("token must be a string.")

    if req_type not in req_types.keys():
        raise ValueError("req_type needs to be one of keys: " + ",".join(req_types.keys()))
    else:
        contact = req_types[req_type]

        try:
            if contact["type"].lower() == "get":
                response = get(contact["adr"], headers=contact["headers"])
            elif contact["type"].lower() == "del":
                response = delete(contact["adr"], headers=contact["headers"])
            elif contact["type"].lower() == "post":
                response = post(contact["adr"], headers=contact["headers"])
            else:
                raise ValueError("not known request method: " + contact["type"])
            # Check if the request was successful (status code 200-299 indicates success)
            if 200 <= response.status_code < 300:
                print("API call was successful. Data filter deleted.")
            else:
                print(f"API call failed. Status code: {response.status_code}")
                print("Response:", response.text)

        except exceptions.RequestException as e:
            print("Error making API call:", e)


