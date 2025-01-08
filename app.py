from common import LoadGoodDataSdk, csv_to_sql
from component import mycomponent

from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from time import time


def st_folder_selector(st_placeholder, path='.', label='Please, select a folder...'):
    # get base path (directory)
    base_path = '.' if path is None or path == '' else path
    base_path = Path(path).resolve()
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


def time_it(ref_time: float=0, run: bool = False):
    """

    :type ref_time: previously taken
    """
    # 2-step function hack
    if not run:
        return time()
    else:
        return time() - ref_time


def main():
    # session variables
    if "analytics" not in st.session_state:
        st.session_state["analytics"] = []
    if "gd" not in st.session_state:
        st.session_state["gd"] = LoadGoodDataSdk(st.secrets["GOODDATA_HOST"], st.secrets["GOODDATA_TOKEN"])

    st.set_page_config(
        layout="wide", page_icon="favicon.ico", page_title="Streamlit-GoodData integration demo"
    )
    org = st.session_state["gd"].organization()

    with st.sidebar:
        ws_list = st.selectbox("Select a workspace", options=[w.name for w in st.session_state["gd"].workspaces])
        st.session_state["analytics"] = st.session_state["gd"].details(wks_id=ws_list, by="name")

        with st.expander("Details"):
            st.write("Hostname:", org.attributes.hostname)
            st.write("Organization id:", org.id)
            st.text(st.session_state["gd"].tree())
            st.write("Identity provider:", org.attributes.oauth_issuer_location)
        with st.expander("Dashboards"):
            ws_dash_list = st.selectbox("Select a dashboard",
                                        [d.title for d in st.session_state["analytics"].analytical_dashboards])
            embed_dashboard = st.button("Embed dashboard")
            display_dashboard = st.button("Display schema")
            # advanced_describe = st.button("Dashboard describe")  # machine learning
        with st.expander("Data actions"):
            df_insight = st.selectbox("Select an Insight",
                                      [d.title for d in st.session_state["analytics"].visualization_objects])
            df_metric = st.selectbox("Select a Dataset", [m.title for m in st.session_state["analytics"].metrics])
            ds_list = st.selectbox("Select a data source",
                                   [d.name for d in st.session_state["gd"].datasources])
            clear_cache = st.button("Clear cache")
            display_insight = st.button("Display an insight")
            display_metric = st.button("Display a metric")
            # advanced_keydriver = st.button("Key driver analysis")
        with st.expander("Data preparation"):
            uploaded_file = st.file_uploader("")
            upload_csv = st.button("Prepare uploaded file")
        with st.expander("Backup & Restore"):
            st.write("Need to find a way to backup and restore using python sdk")
            backup = st.button("Backup selected workspace")
            # backup_ldm = st.download_button("Backup data model for selected workspace", st.session_state["analytics"])
            # backup_analytics = st.download_button("Backup analytics for selected workspace", st.session_state["analytics"])

    active_ws = st.session_state["gd"].specific(ws_list, of_type="workspace", by="name")
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
    elif embed_dashboard:
        t = time_it()
        active_dash = st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id)
        st.write(
            f"connecting to: {st.secrets['GOODDATA_HOST']}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700")
        components.iframe(
            f"{st.secrets['GOODDATA_HOST']}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700",
            1000, 700)
        st.write(f"dashboard loaded in {time_it(t, True)*1000} milliseconds")
    elif display_dashboard:
        # active_dash = st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id)
        # st.write(f"Selected dashboard: {active_dash}")
        # dashboard_visual = generate_graph(active_dash.to_dict())
        dashboard_visual = st.session_state["gd"].schema(ws_dash_list, ws_id=active_ws.id)
        st.graphviz_chart(dashboard_visual)
    # elif advanced_describe:
    # active_ins = st.session_state["gd"].specific(df_insight, of_type="insight", by="name", ws_id=active_ws.id)
    # st.write("Selected dashboard: " + ws_dash_list)
    # st.write(st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id))
    # st.write(generate_nlg_summary(active_ins))
    elif display_metric:
        active_ds = st.session_state["gd"].specific(df_metric, of_type="metric", by="name", ws_id=active_ws.id)
        st.write(f"Selected metric: {active_ds}")
    elif display_insight:
        t = time_it()
        active_ins = st.session_state["gd"].specific(df_insight, of_type="insight", by="name", ws_id=active_ws.id)
        st.write(f"Visualization loaded in {'%.2f' % (time_it(t, True) * 1000)} milliseconds")
        st.dataframe(active_ins)
        # st.write(ProfileReport(active_ins, title="Pandas Profiling Report"))
    # elif advanced_keydriver:
    # st.write("Advanced keydriver")
    elif upload_csv and uploaded_file is not None:
        st.write(
            "Create a new SQL dataset and paste the SQL query (final version should post it directly to the model)")
        st.write(csv_to_sql(uploaded_file))  # limit of 200 rows by default    
    # elif admin_udetail:
    #     active_user = st.session_state["gd"].specific(admin_users, of_type="user", by="id")
    #     active_group = st.session_state["gd"].specific(admin_groups, of_type="group", by="id")
    #     st.write("User details: ", active_user)
    # elif admin_gdetail:
    #     active_user = st.session_state["gd"].specific(admin_users, of_type="user", by="id")
    #     active_group = st.session_state["gd"].specific(admin_groups, of_type="group", by="id")
    #     st.write("Group details: ", active_group)
    #     st.write("Users in the group:", st.session_state["gd"].users_in_group(admin_groups))
    else:
        st.write(f"Selected workspace: {active_ws}")


if __name__ == "__main__":
    main()
