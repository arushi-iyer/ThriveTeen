
# Teen Wellness App (US11p) — Ollama Edition

This package modifies the original teen calorie tracker to remove OpenAI/LangChain dependencies
and adds a **free local chat coach** powered by **Ollama**, plus a simple **Hydration Tracker**.

## New Features
- **Coach Chat (local)**: Uses your local Ollama server (`http://127.0.0.1:11434`) and any installed model
  (e.g., `llama3.1`, `mistral`, `qwen2.5`). No API keys required.
- **Hydration Tracker**: Session-based tracker with a daily goal; when the goal is reached, it calls the
  Activities API to award a "Hydration Goal Met" badge.

## Run
1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the API (HTTPS self-signed by default) in one terminal:
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8030 --ssl-keyfile ./key.pem --ssl-certfile ./cert.pem
   ```
3. Start the UI in another terminal:
   ```bash
   streamlit run demo/app.py --server.port 8501 --server.address 0.0.0.0
   ```
4. For the chat coach, run Ollama locally in a third terminal:
   ```bash
   ollama serve
   ollama pull llama3.1
   ```

## Notes
- The hydration tracker state resets per user session; to persist, add a backend table and endpoint.
- If you don't run HTTPS for the API, set the UI to not verify certificates via the toggle.
