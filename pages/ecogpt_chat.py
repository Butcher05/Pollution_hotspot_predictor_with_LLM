"""
pages/1_EcoGPT_Chat.py  -- Page 2: EcoGPT chatbot

This is your existing chatbot logic, unchanged, just moved into the
multipage app structure. Requires the `chatbot/` package (filters.py,
llm_handler.py) to sit at the PROJECT ROOT, as a sibling of app.py --
Streamlit's pages/ scripts share the same Python path as the main app,
so the existing `from chatbot.xxx import ...` imports keep working
exactly as they did before.
"""

import streamlit as st

from chatbot.filters import is_environment_question
from chatbot.llm_handler import get_response

st.set_page_config(page_title="EcoGPT", page_icon="💬", layout="wide")

st.title("💬 EcoGPT")
st.subheader("Environmental Intelligence Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

prompt = st.chat_input("Ask about AQI, pollution, sustainability, climate or nature")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    if not is_environment_question(prompt):
        answer = (
            "I am an environmental assistant and can only answer "
            "questions related to environment, sustainability, "
            "climate, pollution, biodiversity, renewable energy "
            "and nature."
        )
    else:
        with st.spinner("Thinking..."):
            answer = get_response(prompt)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.write(answer)