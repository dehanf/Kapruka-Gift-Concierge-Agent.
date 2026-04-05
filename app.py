"""
app.py — Kapruka Gift Concierge · Streamlit UI
Run with: streamlit run app.py
"""

import json
import time
import streamlit as st
from agents.router import Router
from memory.semantic_memory import SemanticMemory

# ── Warmup ────────────────────────────────────────────────────────────────────
@st.cache_resource
def _warmup():
    from infrastructure.db.qdrant_store import get_client
    from memory.lt_memory import encoder
    get_client()
    encoder.encode("warmup", show_progress_bar=False)

_warmup()
# ─────────────────────────────────────────────────────────────────────────────

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Kapruka Gift Concierge",
    page_icon="🎁",
    layout="wide",
)

# ── Styling ───────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    [data-testid="stSidebar"] { background-color: #161b27; border-right: 1px solid #2a2f3e; }
    [data-testid="stChatInput"] textarea {
        background-color: #1e2433;
        color: #e8eaf6;
        border: 1px solid #3a4060;
        border-radius: 12px;
    }
    [data-testid="stChatMessageContent"]:has(> div[data-testid="stMarkdownContainer"]) {
        border-radius: 16px;
    }
    .info-card {
        background: #1e2433;
        border: 1px solid #2a3050;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 10px;
        font-size: 0.88rem;
        color: #c8cfe8;
    }
    .info-card strong { color: #7986cb; }
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 2px;
    }
    .badge-search     { background: #1a3a5c; color: #64b5f6; }
    .badge-pref       { background: #1a3d2b; color: #66bb6a; }
    .badge-logistics  { background: #3d2b1a; color: #ffa726; }
    .latency-chip {
        font-size: 0.72rem;
        color: #546e7a;
        margin-top: 4px;
    }
    .concierge-header {
        text-align: center;
        padding: 8px 0 4px 0;
    }
    .concierge-header h1 { font-size: 1.6rem; color: #e8eaf6; margin: 0; }
    .concierge-header p  { color: #546e7a; font-size: 0.85rem; margin: 0; }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────

def _init_state():
    if "customer_id" not in st.session_state:
        st.session_state.customer_id = None
    if "router" not in st.session_state:
        st.session_state.router = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "debug_log" not in st.session_state:
        st.session_state.debug_log = []

_init_state()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎁 Gift Concierge")
    st.markdown("---")

    st.markdown("### Customer ID")
    cid_input = st.text_input(
        "Enter your ID",
        value=st.session_state.customer_id or "",
        placeholder="e.g. 001",
        label_visibility="collapsed",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start", use_container_width=True, type="primary"):
            if cid_input.strip():
                st.session_state.customer_id = cid_input.strip()
                st.session_state.router = Router(customer_id=st.session_state.customer_id)
                st.session_state.messages = []
                st.session_state.debug_log = []
                st.rerun()
    with col2:
        if st.button("Reset", use_container_width=True):
            for key in ["customer_id", "router", "messages", "debug_log"]:
                st.session_state[key] = None if key != "messages" and key != "debug_log" else []
            st.rerun()

    st.markdown("---")

    if st.session_state.customer_id:
        st.markdown("### Saved Profiles")
        sm = SemanticMemory()
        cid = st.session_state.customer_id
        profiles = sm.profiles.get(cid, {})

        if profiles:
            for recipient, data in profiles.items():
                with st.expander(f"👤 {recipient.title()}"):
                    if data.get("allergies"):
                        st.markdown(f"**Allergies:** {', '.join(data['allergies'])}")
                    if data.get("preferences"):
                        st.markdown(f"**Preferences:** {', '.join(data['preferences'])}")
                    if data.get("location"):
                        st.markdown(f"**Location:** {data['location']}")
        else:
            st.caption("No profiles saved yet.")

    st.markdown("---")

    if st.session_state.debug_log:
        st.markdown("### Last Classification")
        last = st.session_state.debug_log[-1]

        badge_map = {
            "SEARCH": "badge-search",
            "PREFERENCE_UPDATE": "badge-pref",
            "LOGISTICS": "badge-logistics",
        }
        badges_html = " ".join(
            f'<span class="badge {badge_map.get(i, "badge-search")}">{i}</span>'
            for i in last.get("intents", [])
        )
        st.markdown(badges_html, unsafe_allow_html=True)

        fields = {
            "Recipient": last.get("search_recipient"),
            "Allergies": json.dumps(last.get("allergies")) if last.get("allergies") else None,
            "Location": last.get("location"),
            "Deadline": last.get("deadline"),
            "Tracking": last.get("tracking_code"),
            "Query": last.get("search_query"),
        }
        rows = "".join(
            f"<div><strong>{k}:</strong> {v}</div>"
            for k, v in fields.items() if v
        )
        if rows:
            st.markdown(f'<div class="info-card">{rows}</div>', unsafe_allow_html=True)


# ── Main chat area ────────────────────────────────────────────────────────────

st.markdown("""
<div class="concierge-header">
  <h1>🎁 Kapruka Gift Concierge</h1>
  <p>Your personal AI gifting assistant for Sri Lanka</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.customer_id:
    st.info("Enter your Customer ID in the sidebar to begin.", icon="👈")
    st.stop()

st.caption(f"Session: **{st.session_state.customer_id}**")
st.markdown("---")

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🎁"):
        st.markdown(msg["content"])
        if msg.get("latency"):
            st.markdown(
                f'<div class="latency-chip">⏱ {msg["latency"]:.2f}s</div>',
                unsafe_allow_html=True,
            )

# ── Chat input ────────────────────────────────────────────────────────────────

user_input = st.chat_input("Ask me anything about gifts, delivery, or save a preference...")

if user_input:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_input)

    # Route and stream response
    with st.chat_message("assistant", avatar="🎁"):

        # Capture classification for sidebar debug panel
        router = st.session_state.router
        original_classify = router.classify_intents
        captured = {}

        def _capturing_classify(message):
            result = original_classify(message)
            captured.update(result)
            return result

        router.classify_intents = _capturing_classify

        t0 = time.time()

        # ← key change: st.write_stream instead of spinner + st.markdown
        response = st.write_stream(router.route_stream(user_input))

        elapsed = time.time() - t0
        router.classify_intents = original_classify

        st.markdown(
            f'<div class="latency-chip">⏱ {elapsed:.2f}s</div>',
            unsafe_allow_html=True,
        )

    # Save to session
    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "latency": elapsed,
    })
    if captured:
        st.session_state.debug_log.append(captured)

    st.rerun()