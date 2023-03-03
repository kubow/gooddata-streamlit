import streamlit as st

from gd_metadata import GdDt


def get_ws_id(name, help):
    for w in help.catalog_workspace.list_workspaces():
        if name == w.name:
            return w.id


def main():
    # set page layout
    st.set_page_config(
        page_title="GoodData visualization app",
        page_icon="✨",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.title("GoodData visualizer")
    # initial settings
    if not "workspaces" in st.session_state:
        st.session_state["workspaces"] = []
    if not "insights" in st.session_state:
        st.session_state["insights"] = []
    if not "meas" in st.session_state:
        st.session_state["meas"] = []
    if not "dims" in st.session_state:
        st.session_state["dims"] = []
    if not "gd" in st.session_state:
        st.session_state["gd"] = GdDt()
    side_endpt = st.sidebar.container()  # GD setup
    side_wrks = st.sidebar.container()   # GD workspaces
    side_flds = st.sidebar.container()   # GD data items
    side_ists = st.sidebar.container()   # GD insights

    with side_endpt:
        st.subheader("Input your Gooddata connection")
        with st.form(key='gd_conn'):
            host = st.text_input(
                "enpoint url")
            token = st.text_input("private api cloud token")
            connect = st.form_submit_button('Connect')

    with side_wrks:
        with st.form(key='gd_wrks'):
            workspace = st.selectbox(
                "Select one of your workspaces",
                options=[w for w in st.session_state['workspaces']],
                key="wks_sel"
            )
            confirm = st.form_submit_button('Select')

    with side_flds:
        with st.form(key='gd_flds'):
            meas = st.multiselect("Select from a list of facts",
                                  [d for d in st.session_state['meas']],
                                  [d for d in st.session_state['meas']]
                                  )
            dims = st.multiselect("Select from a list of attributes",
                                  [d for d in st.session_state['dims']],
                                  [d for d in st.session_state['dims']]
                                  )
            build = st.form_submit_button("Build up your data")

    if build:
        series = st.session_state["gd"].get_content('series')
        frames = st.session_state["gd"].get_content('frames')
        st.write(f'These values are selected: {meas} / {dims}')
        ms = {str(m).split('/')[0]: str(m) for m in meas}
        ds = {str(d).split('/')[0]: str(d) for d in dims}
        indexed_df = frames.indexed(index_by=ms, columns=ds)
        # indexed_series = series.indexed(
        #     index_by=dims[0], data_by=meas[0])
        # indexed_series = series.indexed(
        #     index_by='label/region', data_by='fact/price')
        # non_indexed_series = series.not_indexed(
        #     data_by='fact/price', granularity='label/region')
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
            st.write('Here we migh be able to export yaml definition')
    elif confirm:
        del st.session_state["meas"][:]
        del st.session_state["dims"][:]
        st.session_state["gd"].set_ws(ws=workspace, type='name')
        for measure in st.session_state["gd"].get_content('metric'):
            st.session_state["meas"].append(measure.obj_id)
        for fact in st.session_state["gd"].get_content('facts'):
            st.session_state["meas"].append(fact)
        for attr in st.session_state["gd"].get_content('attrs'):
            st.session_state["dims"].append(attr)
        st.write(f'Measures (Facts & Metrics): {st.session_state["meas"]}')
        st.write(f'Dimensions (Attributes): {st.session_state["dims"]}')
    elif connect:
        st.session_state["gd"].activate(host, token)
        if len(st.session_state["workspaces"]) > 0:
            st.session_state["workspaces"] = []
        for w in st.session_state["gd"].get_content():
            st.session_state["workspaces"].append(w.name)
    else:
        st.write("Please config GoodData instance and select proper items.")


if __name__ == "__main__":
    main()
