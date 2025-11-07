# import time

from fpdf import FPDF  # temporary pdf handling
from gooddata_sdk import (GoodDataSdk, CatalogDataSourcePermissionAssignment,
                          # CatalogDeclarativeDashboardPermissionsForAssignee, CatalogAssigneeRule,
                          CatalogAssigneeIdentifier, CatalogPermissionAssignments,
                          CatalogPermissionsForAssigneeRule, CatalogPermissionsForAssigneeIdentifier,
                          CatalogWorkspace, CatalogWorkspacePermissionAssignment, CatalogUser, CatalogUserGroup)
from gooddata_pandas import GoodPandas
import graphviz
from json import dumps
import math

from gooddata_sdk.catalog.workspace.declarative_model.workspace.analytics_model.analytics_model import \
    CatalogDeclarativeAnalyticsLayer
from pandas import read_csv
from pathlib import Path
from tabulate import tabulate
from treelib import Tree


class LoadGoodDataSdk:
    # abstract level wrapper for GoodData Python SDK
    def __init__(self, gd_host: str = "", gd_token: str = ""):
        print(
            "--- Using SEE GoodData wrapper with some helpers ---"
            "Your workspace environment variables:\n",
            f"GOODDATA_HOST: {gd_host} / GOODDATA_API_TOKEN: {len(gd_token)} characters",
        )
        if gd_host:
            self._sdk = GoodDataSdk.create(gd_host, gd_token)
            self._gp = GoodPandas(gd_host, gd_token)
            self._df = None
            self.workspaces = self._sdk.catalog_workspace.list_workspaces()
            self.datasources = self._sdk.catalog_data_source.list_data_sources()
            try:
                self.users = (
                    self._sdk.catalog_user.list_users()
                )  # alternative get_declarative_users()
                self.groups = self._sdk.catalog_user.list_user_groups()
                self.admin = True
            except Exception as ex:
                self.admin = False
                print(ex)

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
                return None
            else:
                if using_pandas:
                    return self._df.for_visualization(visualization_id=vis_id)
                else:
                    x = self._sdk.visualizations.get_visualization(workspace_id=ws_id, visualization_id=vis_id)
                    return self._sdk.tables.for_visualization(workspace_id=ws_id, visualization=x)

    def details(self, wks_id: str = "", by: str = "id") -> CatalogDeclarativeAnalyticsLayer | None:
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
        return None

    def get_id(self, name, of_type, main=""):
        if not name:
            return None
        if of_type == "user":
            return [u.id for u in self.users if name == u.name][0]
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
            return None

    def organization(self):
        # pretty(self._sdk.catalog_organization.get_organization().to_dict())
        return self._sdk.catalog_organization.get_organization()

    def identity_provider(self):
            return f"Identity provider:{self._sdk.catalog_organization.get_declarative_identity_providers()[0].id}"

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
        return None

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

    def ws_schema(self, ws_id):
        """
        Convert CatalogDependentEntitiesResponse to a Pyvis network graph.
        """
        # Define hierarchy of node importance
        NODE_PRIORITIES = {
            "dataset": 1,  # Most important
            "analyticalDashboard": 2,
            "visualizationObject": 2,
            "metric": 2,
            "fact": 3,
            "attribute": 4  # Least important # Labels not considered here
        }

        # Define colors for node types
        NODE_COLORS = {
            "dataset": "#FF5733",  # Bright red (Core)
            "analyticalDashboard": "#2ECC40",  # Green (Descriptive)
            "visualizationObject": "#3498DB",  # Blue (Measurable)
            "metric": "#9B59B6",  # Purple
            "fact": "#F1C40F",  # Yellow
            "attribute": "#95A5A6"  # Gray
        }

        # Define node sizes based on importance
        NODE_SIZES = {
            "dataset": 50,
            "analyticalDashboard": 40,
            "visualizationObject": 40,
            "metric": 40,
            "fact": 30,
            "attribute": 25
        }

        ws_net = self._sdk.catalog_workspace_content.get_dependent_entities_graph(ws_id)
        elements = []

        # Add nodes
        for node in ws_net.graph.nodes:
            if "." in node.id:
                node_id = node.id.split(".")[0]
            else:
                node_id = node.id
            if check_node_id(node_id, elements):
                print("element present, skipping", node_id)
                continue
            elements.append({
                "data": {
                    "id": node_id,
                    "label": node.title,
                    "type": node.type,
                    "importance": NODE_PRIORITIES.get(node.type, 5)  # Default to 0
                },
                "style": {
                    "background-color": NODE_COLORS.get(node.type, "#999"),
                    "width": NODE_SIZES.get(node.type, 20),
                    "height": NODE_SIZES.get(node.type, 20),
                    "font-size": "12px"
                }
            })

        # Add edges
        for edge in ws_net.graph.edges:
            source, target = edge
            if "." in source.id or "." in target.id:
                continue
            # source = source.split(".")[0]
            # target = target.split(".")[0]
            elements.append({"data": {"source": source.id, "target": target.id}})

        return dumps(elements)

    def schema(self, dashboard_name, ws_id):
        """
        Create a Dashboard schema by parsing its sections and visuals
        """
        schema = graphviz.Digraph()
        schema.attr(ratio='0.5', fontsize="25")
        temp = self.specific(dashboard_name, of_type="dashboard", by="name", ws_id=ws_id)

        root = temp.title
        # Create nodes for each section
        for section in temp.content['layout']['sections']:  # IDashboardLayoutSection
            if 'header' in section and len(section['header']) > 0:
                schema.edge(root, f"Section-{section['header']['title']}")
                sec_root = f"Section-{section['header']['title']}"
            else:
                sec_root = root
            for item in section['items']:  # IDashboardLayoutItem
                if item['widget']['type'] == "insight":
                    if 'title' in item['widget']:
                        schema.edge(sec_root, f"Insight-{item['widget']['title']}")
                    else:
                        print(f"no title in Insight {item['widget']}")
                elif item['widget']['type'] == "richText":
                    schema.edge(sec_root, "RichText")
                else:
                    print(f"unknown thing on dashboard: {item['widget']}")

        return schema

    def users_in_group(self, group_id):
        # return users that belong to a specific group
        listed = [user for user in self.users if user.relationships for group in user.relationships.user_groups.data if
                  group and group.id == group_id]
        return listed

    # ---------- LDM helpers ----------
    def get_declarative_ldm(self, wks_id: str):
        """Return the declarative LDM for a workspace via SDK."""
        return self._sdk.catalog_workspace_content.get_declarative_ldm(wks_id)

    def ldm_overview(self, wks_id: str) -> tuple[list[dict], list[dict]]:
        """Return (datasets_rows, columns_rows) flattened from declarative LDM.

        Each dataset row contains: dataset_id, dataset_title, description, tags.
        Each column row contains: dataset_id, dataset_title, column_id, column_title,
        column_description, tags, data_type, source_column, source_table, column_type,
        granularity, label.
        """
        datasets_rows: list[dict] = []
        columns_rows: list[dict] = []
        try:
            ldm = self.get_declarative_ldm(wks_id)
            ds_list = getattr(getattr(ldm, "ldm", None), "datasets", []) or []
            for ds in ds_list:
                ds_id = getattr(ds, "id", None)
                ds_title = getattr(ds, "title", None) or getattr(ds, "name", None)
                datasets_rows.append({
                    "dataset_id": ds_id,
                    "dataset_title": ds_title,
                    "description": getattr(ds, "description", None),
                    "tags": getattr(ds, "tags", None),
                })
                # Attributes
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
                    })
                # Facts
                for fact in getattr(ds, "facts", []) or []:
                    cdict = getattr(fact, "to_dict", None)
                    as_dict = cdict() if callable(cdict) else getattr(fact, "__dict__", {})
                    src_col_val = as_dict.get("source_column") if isinstance(as_dict, dict) else None
                    src_table = None
                    if isinstance(src_col_val, dict):
                        src_table = src_col_val.get("table") or src_col_val.get("name") or src_col_val.get("dataset")
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
                    })
        except Exception:
            # Return what we have; callers can handle empty lists
            pass
        return datasets_rows, columns_rows


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


def check_node_id(node_id, list_of_objects):
    for obj in list_of_objects:
        if 'data' in obj and 'id' in obj['data']:
            if obj['data']['id'] == node_id:
                return True  # Found the node_id
    return False  # node_id no

def dataframe_to_pdf(dataframe, pdf_path, num_pages):
    rows_per_page = math.ceil(len(dataframe) / num_pages)
    pdf = FPDF()
    for page in range(num_pages):
        start_idx = page * rows_per_page
        end_idx = min((page + 1) * rows_per_page, len(dataframe))
        page_df = dataframe.iloc[start_idx:end_idx]
        pdf.add_page()
        # Convert DataFrame to a formatted table
        table = tabulate(page_df, headers='keys', tablefmt='grid', showindex=False)
        # Add the table to the PDF
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, table)
    # Save the PDF
    pdf.output(pdf_path)


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


if __name__ == "__main__":
    # host, token, sdk = init_gd()
    gooddata = LoadGoodDataSdk()
    for gd_user in gooddata.users:
        print(f"user {gd_user.id} with relations {gd_user.relationships}")
    gooddata.tree()
