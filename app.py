
import streamlit as st
from component import mycomponent

def main():
    st.set_page_config(
        layout="wide", page_icon="favicon.ico", page_title="Streamlit-GoodData integration demo"
    )
    st.sidebar.success("Select a demo above.")
    value = mycomponent(my_input_value="hello there")
    st.write("Received", value)

if __name__ == "__main__":
    main()
