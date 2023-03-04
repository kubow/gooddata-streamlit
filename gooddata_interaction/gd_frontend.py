import streamlit as st

from gd_metadata import GdDt


def main():
    # 1 - initial selections and class variable
    if not "sels" in st.session_state:
        st.session_state["sels"] = {
            "meas": [],
            "dims": [],
            "visu": []
        }
    if not "gd" in st.session_state:
        st.session_state["gd"] = GdDt()

    # 2 - set page layout
    st.set_page_config(
        page_title="GoodData visualization app",
        page_icon="✨",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("GoodData visualizer")
    sidebar_cont = {
        "endpt": st.sidebar.container(),
        "wrksp": st.sidebar.container(),
        "insgt": st.sidebar.container(),
        "field": st.sidebar.container()
    }

    with sidebar_cont["endpt"]:  # Initial connection setup
        st.subheader("Input your Gooddata connection")
        with st.form(key="gd_conn"):
            host = st.text_input("enpoint url")
            token = st.text_input("private api cloud token")
            connect = st.form_submit_button("Connect")
    with sidebar_cont["wrksp"]:  # Workspaces selector
        with st.form(key="gd_wrks"):
            workspace = st.selectbox(
                "Select one of your workspaces",
                options=[w for w in st.session_state["gd"].list()],
                key="wks_sel"
            )
            confirm = st.form_submit_button("Select")
    with sidebar_cont["insgt"]:  # Available insights
        with st.form(key="gd_ists"):
            ists = st.multiselect("Select from list of insights",
                                  [d for d in st.session_state["sels"]["visu"]],
                                  [d for d in st.session_state["sels"]["visu"]]
                                  )
            replicate = st.form_submit_button("Build an insight")
    with sidebar_cont["field"]:  # Available data fields
        with st.form(key="gd_flds"):
            meas = st.multiselect("Select from a list of facts",
                                  [d for d in st.session_state["sels"]["meas"]],
                                  [d for d in st.session_state["sels"]["meas"]]
                                  )
            dims = st.multiselect("Select from a list of attributes",
                                  [d for d in st.session_state["sels"]["dims"]],
                                  [d for d in st.session_state["sels"]["dims"]]
                                  )
            build = st.form_submit_button("Build up your data")

    # 3 - act if button pressed
    if build:  # CASE selected custom fields to visualize
        series = st.session_state["gd"].list("series")
        frames = st.session_state["gd"].list("frames")
        st.write(f"These values are selected: {meas} / {dims}")
        ms = {str(m).split("/")[0]: str(m) for m in meas}
        ds = {str(d).split("/")[0]: str(d) for d in dims}
        indexed_df = frames.indexed(index_by=ms, columns=ds)
        # indexed_series = series.indexed(
        #     index_by=dims[0], data_by=meas[0])
        # indexed_series = series.indexed(
        #     index_by="label/region", data_by="fact/price")
        # non_indexed_series = series.not_indexed(
        #     data_by="fact/price", granularity="label/region")
        tab_bch, tab_lch, tab_ach, tab_data = st.tabs(
            ["Bar Chart", "Line Chart", "Area Chart", "Table"])
        with tab_bch:
            st.bar_chart(indexed_df)
        with tab_lch:
            st.line_chart(indexed_df)
        with tab_ach:
            st.area_chart(indexed_df)
        with tab_data:
            st.dataframe(indexed_df)
            # TODO: tools to export
            st.write("Here we migh be able to export yaml definition")
    elif replicate:  # CASE visualize insight
        st.session_state["gd"].select(id=replicate, type="title")
        print(st.session_state["gd"].get_object("visual"))
    elif confirm:  # CASE GD.C(N) connected
        del st.session_state["sels"]["meas"][:]
        del st.session_state["sels"]["dims"][:]
        del st.session_state["sels"]["visu"][:]
        st.session_state["gd"].select(id=workspace, type="name")
        st.session_state["sels"]["meas"] = st.session_state["gd"].list(
            "metric")
        st.session_state["sels"]["meas"].append(
            st.session_state["gd"].list("fact"))
        st.session_state["sels"]["dims"] = st.session_state["gd"].list(
            "attr")
        st.session_state["sels"]["visu"] = st.session_state["gd"].list(
            "insight")
        st.write(
            f"Measures (Facts & Metrics): {st.session_state['sels']['meas']}")
        st.write(
            f"Dimensions (Attributes): {st.session_state['sels']['dims']}")
        st.write(
            f"Insights (Visualizations): {st.session_state['sels']['visu']}")
    elif connect:  # CASE connect to GD.C(N)
        try:
            st.session_state["gd"].activate(host, token)
            print("Activated connection to gooddata succesfully")
        except Exception as e:
            print(f"Something happened...{e}")
    else:
        st.write("Please config GoodData instance and select proper items.")


if __name__ == "__main__":
    main()
