import streamlit as st
import html as _html


from auth.auth_manager import get_display_name


def render_navbar(show_features: bool = True):
    logged_in = st.session_state.get("user_email") is not None

    with st.container(key="navbar_wrap"):
        col1, col2, col3 = st.columns([3, 2, 4])

        with col1:
            st.markdown(
                '<div class="navbar-brand">🎬 <span>AI Video Assistant</span></div>',
                unsafe_allow_html=True,
            )

        with col2:
            if show_features:
                st.markdown(
                    '<div class="navbar-link-wrap"><a class="navbar-link" href="#what-it-does">Features</a></div>',
                    unsafe_allow_html=True,
                )

        with col3:
            if logged_in:
                display_name = get_display_name(st.session_state.user_email)
                c1, c2, c3 = st.columns([1.5, 1.3, 1.2])
                with c1:
                    # display_name has no character restrictions at signup,
                    # so a stray < or > would otherwise render as raw HTML
                    # here (unsafe_allow_html=True).
                    st.markdown(
                        f"<div class='navbar-user'>👤 {_html.escape(display_name)}</div>",
                        unsafe_allow_html=True,
                    )
                with c2:
                    if st.button("Dashboard", key="navbar_dash", use_container_width=True, type="primary"):
                        st.session_state.page = "dashboard"
                        st.rerun()
                with c3:
                    if st.button("Log out", key="navbar_logout", use_container_width=True):
                        from utils.chat_sessions import save_session
                        save_session(
                            st.session_state.get("user_email", ""),
                            st.session_state.get("chat_history", []),
                            st.session_state.get("result"),
                        )
                        for key in ["user_email", "result", "chat_history", "dash_nav"]:
                            st.session_state.pop(key, None)
                        st.session_state.page = "home"
                        st.rerun()
            else:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Log in", key="navbar_login", use_container_width=True):
                        st.session_state.page = "login"
                        st.rerun()
                with c2:
                    if st.button("Sign up", key="navbar_signup", use_container_width=True, type="primary"):
                        st.session_state.page = "signup"
                        st.rerun()