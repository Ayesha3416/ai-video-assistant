import streamlit as st
import uuid
import html as _html
from utils.chat_sessions import get_sessions, delete_session
from core.rag_engine import build_rag_chain
from auth.auth_manager import get_display_name, is_admin, update_display_name, change_password

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
            st.session_state.pop("_delete_dialog_shown_for", None)
            st.rerun()
    with col2:
        if st.button("Delete", type="primary", use_container_width=True):
            delete_session(st.session_state.get("user_email", ""), session_id)
            st.session_state.confirm_delete_id = None
            st.session_state.pop("_delete_dialog_shown_for", None)
            st.rerun()

def render_sidebar():
    email = st.session_state.get("user_email", "")
    display_name = get_display_name(email) if email else ""
    avatar_letter = display_name[0].upper() if display_name else "?"

    if "current_session_id" not in st.session_state:
        st.session_state.current_session_id = str(uuid.uuid4())

    if st.session_state.get("confirm_delete_id"):
        current_id = st.session_state["confirm_delete_id"]

        # Bug fix: the dialog's Cancel/Delete buttons already clear
        # confirm_delete_id before rerunning. But Streamlit's built-in "X"
        # close button on st.dialog reruns the script WITHOUT running any of
        # our button code, so confirm_delete_id stayed set and this block
        # reopened the same dialog immediately -- clicking X looked like it
        # did nothing. _delete_dialog_shown_for marks "we already displayed
        # the dialog for this id once"; if we get back here with the same id
        # and neither button cleared it, that means it was dismissed via X
        # (or something else closed it) -- treat that as an implicit cancel.
        if st.session_state.get("_delete_dialog_shown_for") == current_id:
            st.session_state.confirm_delete_id = None
            st.session_state.pop("_delete_dialog_shown_for", None)
        else:
            target = next(
                (s for s in get_sessions(email) if s["id"] == current_id),
                None,
            )
            if target:
                st.session_state._delete_dialog_shown_for = current_id
                _confirm_delete_dialog(target["id"], target.get("title", "this chat"))
            else:
                st.session_state.pop("confirm_delete_id", None)
                st.session_state.pop("_delete_dialog_shown_for", None)

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

            from ui.flashcards_page import nav_label as _flashcards_nav_label  # Step 3
            nav_items = [
                # "Results" was previously unreachable: ui/dashboard.py had a
                # full Summary/Action Items/Key Decisions/Transcript/Export
                # view behind `nav == "Results"`, but nothing ever set
                # dash_nav to "Results" -- this button is the fix.
                ("Results", "Results", ":material/description:"),
                (_flashcards_nav_label(email), "Flashcards", ":material/style:"),  # Step 3
                ("Stats", "Stats", ":material/bar_chart:"),
                ("History", "History", ":material/history:"),
            ]
            if is_admin(email):
                nav_items.append(("Admin", "Admin", ":material/shield_person:"))

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
                # display_name/email have no character restrictions at
                # signup, so a stray < or > would otherwise render as raw
                # HTML here (this is unsafe_allow_html=True). st.popover's
                # own label above is a widget label, not markdown, so it's
                # unaffected -- only this explicit div needs escaping.
                st.markdown(
                    f"<div class='profile-popup-email'>{_html.escape(email)}</div>",
                    unsafe_allow_html=True,
                )

                # Same flash-message pattern ui/auth_pages.py already uses
                # for signup->login: set the message, then st.rerun() --
                # st.success() called immediately before a rerun would never
                # actually get painted to the screen (the rerun cancels the
                # current render before the browser sees it), so it has to
                # be shown on the FOLLOWING render instead.
                if "profile_flash_message" in st.session_state:
                    st.success(st.session_state.pop("profile_flash_message"))

                st.markdown("<hr class='sidebar-hr'>", unsafe_allow_html=True)

                with st.expander("✏️  Edit display name"):
                    with st.form("edit_name_form"):
                        new_name = st.text_input(
                            "Display name", value=display_name, key="edit_name_input"
                        )
                        name_submitted = st.form_submit_button(
                            "Save name", use_container_width=True
                        )
                    if name_submitted:
                        ok, msg = update_display_name(email, new_name)
                        if ok:
                            st.session_state.profile_flash_message = msg
                            st.rerun()
                        else:
                            st.error(msg)

                with st.expander("🔒  Change password"):
                    with st.form("change_pw_form", clear_on_submit=True):
                        current_pw = st.text_input(
                            "Current password", type="password", key="current_pw_input"
                        )
                        new_pw = st.text_input(
                            "New password (min 8 characters)",
                            type="password", key="new_pw_input",
                        )
                        confirm_pw = st.text_input(
                            "Confirm new password", type="password", key="confirm_pw_input"
                        )
                        pw_submitted = st.form_submit_button(
                            "Change password", use_container_width=True
                        )
                    if pw_submitted:
                        if not current_pw or not new_pw or not confirm_pw:
                            st.error("Please fill in all three fields.")
                        elif new_pw != confirm_pw:
                            st.error("New passwords don't match.")
                        else:
                            ok, msg = change_password(email, current_pw, new_pw)
                            if ok:
                                st.session_state.profile_flash_message = msg
                                st.rerun()
                            else:
                                st.error(msg)

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