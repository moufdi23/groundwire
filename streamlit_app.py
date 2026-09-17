import uuid
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000/chat"

st.set_page_config(page_title="Groundwire — Supabase Support Agent", page_icon="🔌")
st.title("Groundwire — Supabase Support Agent")

# One thread_id per browser session — ties into the PostgresSaver checkpointer.
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role", "content", "meta"}

# Replay the conversation on each rerun.
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("meta"):
            meta = msg["meta"]
            parts = [f"`{meta['path_taken']}`"]
            if meta.get("needs_escalation"):
                parts.append("⚠️ escalation flagged")
            if meta.get("ticket_id") is not None:
                parts.append(f"ticket #{meta['ticket_id']}")
            st.caption("  ·  ".join(parts))

# Chat input at the bottom.
user_input = st.chat_input("Ask a Supabase question…")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input, "meta": None})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                resp = requests.post(
                    API_URL,
                    json={"message": user_input, "thread_id": st.session_state.thread_id},
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                answer = data["answer"]
                meta = {
                    "path_taken": data.get("path_taken", ""),
                    "needs_escalation": data.get("needs_escalation", False),
                    "ticket_id": data.get("ticket_id"),
                }
            except requests.exceptions.ConnectionError:
                answer = "Backend not reachable — is uvicorn running? (`uvicorn scripts.api:app --reload`)"
                meta = None
            except requests.exceptions.Timeout:
                answer = "Request timed out after 60 s. The agent may still be processing — try again."
                meta = None
            except requests.exceptions.HTTPError as exc:
                answer = f"API error {exc.response.status_code}: {exc.response.text}"
                meta = None

        st.markdown(answer)
        if meta:
            parts = [f"`{meta['path_taken']}`"]
            if meta.get("needs_escalation"):
                parts.append("⚠️ escalation flagged")
            if meta.get("ticket_id") is not None:
                parts.append(f"ticket #{meta['ticket_id']}")
            st.caption("  ·  ".join(parts))

    st.session_state.messages.append({"role": "assistant", "content": answer, "meta": meta})
