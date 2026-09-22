import streamlit as st
import uuid
from utils.chat_sessions import get_sessions, delete_session
from core.rag_engine import build_rag_chain
from auth.auth_manager import get_display_name

def _load_session(session: dict):
    st.session_state.chat_history = session.get("chat_history", [])
    st.session_state.current_session_id = session.get("id", str(uuid.uuid4()))
    saved_result = session.get("result")
    if saved_result:
        result = dict(saved_result)
        result["rag_chain"] = None
        st.session_state.result = result
    else:
        st.session_state.result = None
    st.session_state._dash_nav_redirect = "Chat"

@st.dialog("Delete chat?")
def _confirm_delete_dialog(session_id: str, title: str):
    st.write(f'Delete "{title}"? This can\'t be undone.')
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.confirm_delete_id = None
            st.rerun()
    with col2:
        if st.button("Delete", type="primary", use_container_width=True):
            delete_session(st.session_state.get("user_email", ""), session_id)
            st.session_state.confirm_delete_id = None
            st.rerun()

def render_sidebar():
    email = st.session_state.get("user_email", "")
    display_name = get_display_name(email) if email else ""
    avatar_letter = display_name[0].upper() if display_name else "?"

    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = str(uuid.uuid4())

    if st.session_state.get("confirm_delete_id"):
        target = next(
            (s for s in get_sessions(email) if s["id"] == st.session_state["confirm_delete_id"]),
            None,
        )
        if target:
            _confirm_delete_dialog(target["id"], target.get("title", "this chat"))
        else:
            st.session_state.pop("confirm_delete_id", None)

    with st.sidebar:
        top_section = st.container(key="top_section")
        with top_section:
            st.markdown('<div class="app-brand">AI Video Assistant</div>', unsafe_allow_html=True)
            st.markdown("<div class='sidebar-brand-spacer'></div>", unsafe_allow_html=True)

        # ---- New / Navigation ----
        if "dash_nav" not in st.session_state:
            st.session_state.dash_nav = "Chat"

        nav_block = st.container(key="nav_block")
        with nav_block:
            if st.button("New Chat", icon=":material/add:", use_container_width=True, key="sidebar_new_chat"):
                st.session_state.result = None
                st.session_state.chat_history = []
                st.session_state.current_session_id = str(uuid.uuid4())
                st.session_state.dash_nav = "Chat"
                st.rerun()

            nav_items = [
                ("Stats", "Stats", ":material/bar_chart:"),
                ("History", "History", ":material/history:"),
            ]

            for label, key_nav, icon in nav_items:
                is_active = st.session_state.dash_nav == key_nav
                if st.button(
                    label,
                    icon=icon,
                    use_container_width=True,
                    key=f"nav_{key_nav}",
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state.dash_nav = key_nav
                    st.rerun()

        st.markdown("<div style='height:0.25rem;'></div>", unsafe_allow_html=True)
        st.markdown("<hr class='sidebar-hr'>", unsafe_allow_html=True)

        # ---- Recent chats ----
        st.markdown("<div class='sidebar-section-label'>Recent</div>", unsafe_allow_html=True)

        sessions = get_sessions(email)

        with st.container(height=260, border=False, key="recent_box"):
            if not sessions:
                st.markdown(
                    "<div class='sidebar-empty-note'>No previous chats yet.</div>",
                    unsafe_allow_html=True,
                )
            else:
                for session in sessions[:30]:
                    label = session.get("title") or "Untitled chat"
                    if len(label) > 22:
                        label = label[:22] + "..."

                    row_col, menu_col = st.columns([5, 1])

                    with row_col:
                        if st.button(label, use_container_width=True, key=f"session_{session['id']}"):
                            _load_session(session)
                            st.rerun()

                    with menu_col:
                        if st.button("⋮", key=f"menu_{session['id']}"):
                            st.session_state.confirm_delete_id = session["id"]
                            st.rerun()

        # ---- Profile (pinned to the bottom of the sidebar) ----
        with st.container(key="profile_section"):
            st.markdown("<hr class='sidebar-hr profile-hr'>", unsafe_allow_html=True)

            with st.popover(f"👤  {display_name}", use_container_width=True):
                st.markdown(
                    f"<div class='profile-popup-email'>{email}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("<hr class='sidebar-hr'>", unsafe_allow_html=True)

                if st.button("🏠  Landing Page", use_container_width=True, key="profile_landing"):
                    st.session_state.page = "home"
                    st.rerun()

                st.markdown("<hr class='sidebar-hr'>", unsafe_allow_html=True)

                if st.button("Log out", use_container_width=True, key="sidebar_logout"):
                    for key in ["user_email", "result", "chat_history", "dash_nav", "current_session_id"]:
                        st.session_state.pop(key, None)
                    st.session_state.page = "home"
                    st.rerun()