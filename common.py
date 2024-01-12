from gooddata_sdk import GoodDataSdk, CatalogWorkspace
from gooddata_pandas import GoodPandas
import streamlit as st
from treelib import Tree


class LoadGoodDataSdk:
    def __init__(self, gd_host: str="", gd_token: str=""):
        print(
            "Your workspace evnironment variables:\n",
            f"GOODDATA_HOST: {gd_host} / GOODDATA_TOKEN: {len(gd_token)} characters",
        )
        if gd_host:
            self._sdk = GoodDataSdk.create(gd_host, gd_token)
            self._gp = GoodPandas(gd_host, gd_token)
            self.users = (
                self._sdk.catalog_user.list_users()
            )  # alternative get_declarative_users()
            self.groups = self._sdk.catalog_user.list_user_groups()
            self.datasources = self._sdk.catalog_data_source.list_data_sources()
            self.workspaces = self._sdk.catalog_workspace.list_workspaces()

    def organization(self):
        print(f"\nCurrent organization info:")  # ORGANIZATION INFO
        pretty(self._sdk.catalog_organization.get_organization().to_dict())
        return self._sdk.catalog_organization.get_organization()
    
    def data(self, ws_id="", for_insight=""):
        if for_insight:
            temp = self._gp.data_frames(ws_id)
            return temp.for_insight(insight_id=for_insight)
        else:
            return self._gp.data_frames(ws_id)

    def details(self, wks_id: str = "", by: str="id") -> []:
        if not wks_id:
            wks_id = self.first(of_type="workspace")
            print("selecting first workspace as no one submitted")
        if by != "id":
            wks_id = self.get_id(wks_id, of_type="workspace")
        return self._sdk.catalog_workspace_content.get_declarative_analytics_model(wks_id).analytics

    def first(self, of_type="user", by="id"):
        if of_type == "user":
            return first_item(self.users, by)
        elif of_type == "group":
            return first_item(self.groups, by)
        elif of_type == "datasource":
            return first_item(self.datasources, by)
        elif of_type == "workspace":
            return first_item(self.workspaces, by)

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
            if not main:
                return None
            else:
                temp = self.details(wks_id=main, by="id")
            if of_type == "insight":
                return [i.id for i in temp.visualization_objects if name == i.title][0]
            elif of_type == "dashboard":
                return [w.id for w in temp.analytical_dashboards if name == w.title][0]
            elif of_type == "metric":
                return [w.id for w in temp.metrics if name == w.title][0]

    def specific(self, value, of_type="user", by="id", ws_id=""):
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
            #return self._sdk.insights.get_insight(value)
            return self.data(ws_id=ws_id, for_insight=value)
        elif of_type == "metric":
            return self._sdk.catalog_workspace_content.get_metrics_catalog(value)
    
    def tree(self) -> Tree:
        tree = Tree()
        tree.create_node("GoodData", "root")
        for workspace in self.workspaces:
            parent_id = workspace.parent_id if workspace.parent_id else "root"
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

def pretty(d, indent=1, char="-"):
    for key, value in d.items():
        if isinstance(value, dict):
            pretty(value, indent + 2)
        else:
            print(f"{char*(indent)} {str(key)} : {str(value)}")


def first_item(dataset, attr=""):
    if len(dataset) < 1:
        return None
    else:
        return next(iter(dataset)).__getattribute__(attr)


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
    # tree.show(line_type="ascii-em")
    return tree


if __name__ == "__main__":
    # host, token, sdk = init_gd()
    gooddata = LoadGoodDataSdk()
    for user in gooddata.users:
        print(f"user {user.id} with relations {user.relationships}")
    visualize_workspace_hierarchy(gooddata._sdk)
