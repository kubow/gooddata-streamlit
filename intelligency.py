from enchant import Dict
from openai import OpenAI
import streamlit as st


def chatbox_generate_backup():
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
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
                model="gpt-3.5-turbo",
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
    spell_checker = Dict("en_US")

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
