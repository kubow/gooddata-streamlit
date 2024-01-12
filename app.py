
from common import LoadGoodDataSdk, visualize_workspace_hierarchy
from component import mycomponent
#from pandas_profiling import ProfileReport
from openai import OpenAI
import streamlit as st
import streamlit.components.v1 as components

def chatbox_generate_backup():
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = "gpt-3.5-turbo"
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            for response in client.chat.completions.create(
                model=st.session_state["openai_model"],
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
                stream=True,
            ):
                full_response += (response.choices[0].delta.content or "")
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})

def main():
    # connect secrets
    gooddata = LoadGoodDataSdk(st.secrets["GOODDATA_HOST"], st.secrets["GOODDATA_TOKEN"])

    # session variables
    if "analytics" not in st.session_state:
        st.session_state["analytics"] = []
    
    st.set_page_config(
        layout="wide", page_icon="favicon.ico", page_title="Streamlit-GoodData integration demo"
    )

    with st.sidebar:
        ws_list = st.selectbox("Select a workspace", options=[w.name for w in gooddata.workspaces])
        st.session_state["analytics"] = gooddata.details(wks_id=ws_list, by="name")
        with st.expander("Embedding"):
            ws_dash_list = st.selectbox("Select a dashboard", [d.title for d in st.session_state["analytics"].analytical_dashboards])
            embed_dashboard = st.button("Embed dashboard")
            display_dashboard = st.button("Display details")
        with st.expander("Data frames"):
            df_insight = st.selectbox("Select an Insight", [d.title for d in st.session_state["analytics"].visualization_objects])
            df_metric = st.selectbox("Select a metric", [m.title for m in st.session_state["analytics"].metrics])
            display_insight = st.button("Display an insight")
            display_metric = st.button("Display a metric")
        advanced_describe = st.button("Dashboard describe")
        advanced_keydriver = st.button("Key driver analysis")

    # decission tree
    active_ws = gooddata.specific(ws_list, of_type="workspace", by="name")
    if embed_dashboard:
        active_dash = gooddata.specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id)
        st.write(f"connecting to: {st.secrets['GOODDATA_HOST']}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700")
        components.iframe(f"{st.secrets['GOODDATA_HOST']}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700", 625, 700)
    elif display_dashboard:
        active_dash = gooddata.specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id)
        st.write(f"Selected dashboard: {active_dash}")
    elif display_metric:
        active_ds = gooddata.specific(df_metric, of_type="metric", by="name", ws_id=active_ws.id)
        st.write(f"Selected metric: {active_ds}")
    elif display_insight:
        active_ins = gooddata.specific(df_insight, of_type="insight", by="name", ws_id=active_ws.id)
        st.dataframe(active_ins)
        
        #st.write(ProfileReport(active_ins, title="Pandas Profiling Report"))
    elif advanced_describe:
        st.write("Selected dashboard: " + ws_dash_list)
        st.write(gooddata.specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id))
    elif advanced_keydriver:
        st.write("Advanced keydriver")
    else:
        st.text(gooddata.tree())
        st.write(f"Selected workspace: {active_ws}")
        
    

if __name__ == "__main__":
    main()
