import streamlit as st
import ollama # or import groq

# Initialize Ollama client or Groq client
client = ollama.Client() 
# or 
# client = groq.Groq(api_key="your_api_key")

st.title("Llama 3 Chatbot")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("Type your message here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get response from Llama 3
    response = client.chat(model="llama3:latest", messages=st.session_state.messages) # for Ollama
    # or
    # response = client.chat.completions.create(model="llama3-8b-8192", messages=st.session_state.messages) # for Groq

    # assistant_response = response.choices[0].message.content # Extract content

    # Placeholder for actual Llama 3 response
    assistant_response = f"You said: {prompt}. (Llama 3 response would go here)" 

    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
    with st.chat_message("assistant"):
        st.markdown(assistant_response)
