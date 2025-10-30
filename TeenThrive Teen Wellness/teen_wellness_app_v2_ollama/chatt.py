import streamlit as st
import ollama

st.title("Llama 3 Chatbot")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle user input
if prompt := st.chat_input("Ask Llama 3..."):
    # Add user message to history and display
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get response from Llama 3 using Ollama
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_stream = ollama.chat(
                model="llama3:latest",
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
                stream=True,
            )
            full_response = ""
            placeholder = st.empty()
            for chunk in response_stream:
                full_response += chunk["message"]["content"]
                placeholder.markdown(full_response + "▌") # Add blinking cursor effect
            placeholder.markdown(full_response)

        # Add assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": full_response})

