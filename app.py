
from common import LoadGoodDataSdk, csv_to_sql
from component import mycomponent
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

def st_folder_selector(st_placeholder, path='.', label='Please, select a folder...'):
    # get base path (directory)
    base_path = '.' if path is None or path is '' else path
    base_path = base_path if os.path.isdir(
        base_path) else os.path.dirname(base_path)
    base_path = '.' if base_path is None or base_path is '' else base_path
    # list files in base path directory
    files = os.listdir(base_path)
    if base_path is not '.':
        files.insert(0, '..')
    files.insert(0, '.')
    selected_file = st_placeholder.selectbox(
        label=label, options=files, key=base_path)
    selected_path = os.path.normpath(os.path.join(base_path, selected_file))
    if selected_file is '.':
        return selected_path
    if os.path.isdir(selected_path):
        selected_path = st_folder_selector(st_placeholder=st_placeholder,
                                         path=selected_path, label=label)
    return selected_path


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
        backup = st.button("Backup selected workspace")
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
        with st.expander("Data preparation"):
            uploaded_file = st.file_uploader("")
            upload_csv = st.button("Prepare uploaded file")
        with st.expander("Administration"):
            admin_users = st.selectbox("Select a user", [u.id for u in st.session_state["gd"].users])
            admin_groups = st.selectbox("Select a group", [g.id for g in st.session_state["gd"].groups])
            admin_udetail = st.button("Display user details")
            admin_gdetail = st.button("Display group details")
        with st.expander("Backup"):
            file_picker = st.file_uploader("")
            upload_csv = st.button("Prepare uploaded file")

    active_ws = st.session_state["gd"].specific(ws_list, of_type="workspace", by="name")
    if backup:
        st.write(st.session_state["gd"].export(active_ws))
    elif embed_dashboard:
        active_dash = st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id)
        st.write(f"connecting to: {st.secrets['GOODDATA_HOST']}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700")
        components.iframe(f"{st.secrets['GOODDATA_HOST']}/dashboards/embedded/#/workspace/{active_ws.id}/dashboard/{active_dash.id}?showNavigation=false&setHeight=700", 1000, 700)
    elif display_dashboard:
        active_dash = st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id)
        st.write(f"Selected dashboard: {active_dash}")
    elif advanced_describe:
        active_ins = st.session_state["gd"].specific(df_insight, of_type="insight", by="name", ws_id=active_ws.id)
        st.write("Selected dashboard: " + ws_dash_list)
        # st.write(st.session_state["gd"].specific(ws_dash_list, of_type="dashboard", by="name", ws_id=active_ws.id))
        # st.write(generate_nlg_summary(active_ins))
    elif display_metric:
        active_ds = st.session_state["gd"].specific(df_metric, of_type="metric", by="name", ws_id=active_ws.id)
        st.write(f"Selected metric: {active_ds}")
    elif display_insight:
        active_ins = st.session_state["gd"].specific(df_insight, of_type="insight", by="name", ws_id=active_ws.id)
        st.dataframe(active_ins)
        #st.write(ProfileReport(active_ins, title="Pandas Profiling Report"))
    elif advanced_keydriver:
        st.write("Advanced keydriver")
    elif upload_csv and uploaded_file is not None:
        st.write("Create a new SQL dataset and paste the SQL query (final version should post it directly to the model)")
        st.write(csv_to_sql(uploaded_file))  # limit of 200 rows by default    
    elif admin_udetail:
        active_user = st.session_state["gd"].specific(admin_users, of_type="user", by="id")
        active_group = st.session_state["gd"].specific(admin_groups, of_type="group", by="id")
        st.write("User details: ", active_user)
    elif admin_gdetail:
        active_user = st.session_state["gd"].specific(admin_users, of_type="user", by="id")
        active_group = st.session_state["gd"].specific(admin_groups, of_type="group", by="id")
        st.write("Group details: ", active_group)
        st.write("Users in the group:", st.session_state["gd"].users_in_group(admin_groups))
    else:
        st.text(st.session_state["gd"].tree())
        st.write(f"Selected workspace: {active_ws}")
        st.write("Connection info", st.session_state["gd"].organization().attributes)
        
    
if __name__ == "__main__":
    main()
