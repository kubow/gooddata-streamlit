from requests import exceptions, get, post, delete
from time import time

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
        <script src="https://unpkg.com/cytoscape-dagre/cytoscape-dagre.js"></script>

        <style>
            #cy {{
                width: 100%;
                height: 600px;
                border: 1px solid black;
            }}
            .tooltip {{
                position: absolute;
                z-index: 1000;
                background: white;
                padding: 5px;
                border-radius: 5px;
                font-size: 20px;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
                display: none;
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
            console.log("cytoscape-dagre:", typeof cytoscapeDagre !== 'undefined' ? "Loaded" : "NOT Loaded");

            // Ensure Dagre extension is available before use
            if (typeof cytoscapeDagre !== 'undefined') {{
                console.log("Registering cytoscape-dagre...");
                cytoscape.use(cytoscapeDagre);
            }} else {{
                console.error("ERROR: cytoscape-dagre did not load properly.");
                return;
            }}

            const elements = {elements_json};

            var cy = cytoscape({{
                container: document.getElementById('cy'),
                elements: elements,
                style: [
                    {{
                        selector: 'node',
                        style: {{
                            'label': 'data(label)',
                            'text-valign': 'center',
                            'color': 'black',
                            'text-halign': 'center',
                            'font-size': '12px',
                            'width': 60,
                            'height': 60,
                            'background-fit': 'contain',
                            'background-color': 'transparent'
                        }}
                    }},
                    {{
                        selector: 'node[type="dataset"]',
                        style: {{
                            'background-image': 'https://raw.githubusercontent.com/kubow/Data_playground/main/image/dataset.png',  // Database icon
                            'background-fit': 'contain',
                            'background-opacity': 0,
                            'shape': 'rectangle',
                            'width': '50px',
                            'height': '50px'
                        }}
                    }},
                    {{
                        selector: 'node[type="attribute"]',
                        style: {{
                            'background-image': 'https://raw.githubusercontent.com/kubow/Data_playground/main/image/attr.png',  // Attribute key icon
                            'background-fit': 'contain',
                            'background-opacity': 0,
                            'shape': 'rectangle',
                            'width': '50px',
                            'height': '50px'
                        }}
                    }},
                    {{
                        selector: 'node[type="fact"], node[type="metric"]',
                        style: {{
                            'background-image': 'https://raw.githubusercontent.com/kubow/Data_playground/main/image/metric.png',  // Bar chart metric icon
                            'background-fit': 'contain',
                            'background-opacity': 0,
                            'shape': 'rectangle',
                            'width': '50px',
                            'height': '50px'
                        }}
                    }},
                    {{
                        selector: 'node[type="visualizationObject"]',
                        style: {{
                            'background-image': 'https://raw.githubusercontent.com/kubow/Data_playground/main/image/visual.png',  // Data visualization icon
                            'background-fit': 'contain',
                            'background-opacity': 1,
                            'shape': 'rectangle',
                            'width': '50px',
                            'height': '50px'
                        }}
                    }},
                    {{
                        selector: 'node[type="analyticalDashboard"]',
                        style: {{
                            'background-image': 'https://raw.githubusercontent.com/kubow/Data_playground/main/image/dashboard.png',  // Dashboard panel icon
                            'background-fit': 'contain',
                            'background-opacity': 1,
                            'shape': 'rectangle',
                            'width': '50px',
                            'height': '50px'
                        }}
                    }},
                    {{
                        selector: 'edge',
                        style: {{
                            'width': 2,
                            'line-color': '#f2f2f2',
                            'target-arrow-shape': 'triangle',
                            'curve-style': 'bezier'
                        }}
                    }}
                ],
                layout: {{
                    name: 'dagre',
                    rankDir: 'TB',  // Top to Bottom layout
                    nodeSep: 50,
                    edgeSep: 20,
                    rankSep: 75
                }}
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


