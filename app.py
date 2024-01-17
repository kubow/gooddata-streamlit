
from common import LoadGoodDataSdk
from component import mycomponent
# from pandasgui import show
# import enchant
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

def generate_nlg_summary(dataframe):
    # Spellchecker initialization
    spell_checker = enchant.Dict("en_US")

    # NLG Summary
    summary = "Here is a summary of your DataFrame:\n\n"

    # General information
    summary += f"The DataFrame has {len(dataframe)} rows and {len(dataframe.columns)} columns.\n\n"

    # Column-wise information
    for column in dataframe.columns:
        col_data = dataframe[column]

        # Basic statistics
        summary += f"Column '{column}':\n"
        summary += f"  - Mean: {col_data.mean()}\n"
        summary += f"  - Median: {col_data.median()}\n"
        summary += f"  - Unique values: {col_data.nunique()}\n"

        # Spellcheck and include a sample of unique values
        sample_values = col_data.sample(min(5, len(col_data))).astype(str)
        sample_values = sample_values.apply(lambda x: spell_checker.suggest(x)[0] if not spell_checker.check(x) else x)
        summary += f"  - Sample values: {', '.join(sample_values)}\n\n"

    return summary

def main():
    # session variables
    if "analytics" not in st.session_state:
        st.session_state["analytics"] = []
    if "gd" not in st.session_state:
        st.session_state["gd"] = LoadGoodDataSdk(st.secrets["GOODDATA_HOST"], st.secrets["GOODDATA_TOKEN"])
    
    st.set_page_config(
        layout="wide", page_icon="favicon.ico", page_title="Streamlit-GoodData integration demo"
    )

    with st.sidebar:
        ws_list = st.selectbox("Select a workspace", options=[w.name for w in st.session_state["gd"].workspaces])
        st.session_state["analytics"] = st.session_state["gd"].details(wks_id=ws_list, by="name")
        with st.expander("Dashboards"):
            ws_dash_list = st.selectbox("Select a dashboard", [d.title for d in st.session_state["analytics"].analytical_dashboards])
            embed_dashboard = st.button("Embed dashboard")
            display_dashboard = st.button("Display details")
            advanced_describe = st.button("Dashboard describe")
        with st.expander("Data frames"):
            df_insight = st.selectbox("Select an Insight", [d.title for d in st.session_state["analytics"].visualization_objects])
            df_metric = st.selectbox("Select a Dataset", [m.title for m in st.session_state["analytics"].metrics])
            display_insight = st.button("Display an insight")
            display_metric = st.button("Display a metric")
        
        advanced_keydriver = st.button("Key driver analysis")

    # decission tree
    active_ws = st.session_state["gd"].specific(ws_list, of_type="workspace", by="name")
    if embed_dashboard:
        active_dash = st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id)
        st.write(f"connecting to: {st.secrets['GOODDATA_HOST']}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700")
        components.iframe(f"{st.secrets['GOODDATA_HOST']}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700", 1000, 700)
    elif display_dashboard:
        active_dash = st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id)
        st.write(f"Selected dashboard: {active_dash}")
    elif display_metric:
        active_ds = st.session_state["gd"].specific(df_metric, of_type="metric", by="name", ws_id=active_ws.id)
        st.write(f"Selected metric: {active_ds}")
    elif display_insight:
        active_ins = st.session_state["gd"].specific(df_insight, of_type="insight", by="name", ws_id=active_ws.id)
        st.dataframe(active_ins)
        
        #st.write(ProfileReport(active_ins, title="Pandas Profiling Report"))
    elif advanced_describe:
        active_ins = st.session_state["gd"].specific(df_insight, of_type="insight", by="name", ws_id=active_ws.id)
        st.write("Selected dashboard: " + ws_dash_list)
        # st.write(st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id))
        # st.write(generate_nlg_summary(active_ins))
    elif advanced_keydriver:
        st.write("Advanced keydriver")
    else:
        st.text(st.session_state["gd"].tree())
        st.write(f"Selected workspace: {active_ws}")
        st.write("Conenction info", st.session_state["gd"].organization().attributes)
        
    
if __name__ == "__main__":
    main()
