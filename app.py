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
    if "timing" not in st.session_state:
        st.session_state["timing"] = []

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
            ds_list = st.selectbox("Select a data source",
                                   [d.name for d in st.session_state["gd"].datasources])
            clear_cache = st.button("Clear cache for selected data source")
            display_insight = st.button("Test Insight Retrieval")
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
            f"connecting to: {st.secrets['GOODDATA_HOST']}dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700")
        components.iframe(
            f"{st.secrets['GOODDATA_HOST']}dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700",
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
    elif display_insight:
        import datetime
        import pandas as pd
        st.info(f"Testing retrieval of insight '{df_insight}' from data source '{ds_list}'...")
        t0 = time_it()
        insight_obj = next((d for d in st.session_state["analytics"].visualization_objects if d.title == df_insight), None)
        if insight_obj is not None:
            try:
                active_ins = st.session_state["gd"].specific(df_insight, of_type="insight", by="name", ws_id=active_ws.id)
                t1 = time_it(t0, True)
                st.success(f"Insight retrieved in {t1:.2f} seconds.")
                # Append timing info
                # Store timestamp as pandas Timestamp for better plotting
                import pandas as pd
                st.session_state["timing"].append({
                    "insight": df_insight,
                    "datasource": ds_list,
                    "timestamp": pd.Timestamp.now(),
                    "elapsed": t1
                })
                # Show time series plot for ALL insights
                if st.session_state["timing"]:
                    timing_df = pd.DataFrame(st.session_state["timing"])
                    timing_df["timestamp"] = pd.to_datetime(timing_df["timestamp"])
                    timing_df = timing_df.sort_values(["insight", "timestamp"])
                    import altair as alt
                    st.caption("Time series of retrieval times for all insights.")
                    chart = alt.Chart(timing_df).mark_line(point=True).encode(
                        x=alt.X('timestamp:T', title='Timestamp'),
                        y=alt.Y('elapsed:Q', title='Retrieval time (s)'),
                        color=alt.Color('insight:N', title='Insight'),
                        tooltip=['insight', 'datasource', 'timestamp', 'elapsed']
                    ).properties(width='container', height=350)
                    st.altair_chart(chart, use_container_width=True)
                    st.dataframe(
                        timing_df[["insight","datasource","timestamp","elapsed"]]
                        .rename(columns={"elapsed":"Retrieval time (s)", "insight": "Insight", "datasource": "Data source", "timestamp": "Timestamp"})
                    )
                # Show the dataframe with the insight's content
                st.caption("Insight object data frame (actual data):")
                st.dataframe(active_ins)

            except Exception as e:
                st.error(f"Error retrieving insight: {e}")
        else:
            st.warning("Selected insight not found.")

    # elif advanced_keydriver:
    # st.write("Advanced keydriver")
    elif upload_csv and uploaded_file is not None:
        if prep_option == "CSV as SQL dataset":
            st.write("Create a new SQL dataset and paste the SQL query (final version should post it directly to the model)")
            st.write(csv_to_sql(uploaded_file))  # limit of 200 rows by default
        elif prep_option == "CSV S3 uploader":
            st.info("[Placeholder] CSV S3 uploader logic will be implemented here.")
        elif prep_option == "LDM preparation":
            st.write("LDM Preparation: Generating request based on CSV fields...")
            st.write(csv_to_ldm_request(uploaded_file))

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
        st.write(f"Selected workspace: {active_ws.name}")
        st.write("Dependent Entities Graph:")
        # Inject Cytoscape HTML into Streamlit
        components.html(html_cytoscape(st.session_state["gd"].ws_schema(active_ws.id)), height=650)



if __name__ == "__main__":
    main()
