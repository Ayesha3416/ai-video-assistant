import streamlit as st
from ui.navbar import render_navbar
from auth.auth_manager import register_user, verify_user


def render_login_page():
    render_navbar(show_features=False)

    if st.button("← Back to Home", key="back_home_login"):
        st.session_state.page = "home"
        st.rerun()

    with st.container(key="auth_container"):
        if "auth_flash_message" in st.session_state:
            st.success(st.session_state.pop("auth_flash_message"))

        with st.container(border=True):
            st.markdown("<h2 style='color:#0f172a; margin-bottom:0.1rem; font-size:1.6rem;'>Welcome back</h2>", unsafe_allow_html=True)
            st.markdown('<p style="color:#64748b; margin-bottom:1.2rem; font-size:0.95rem;">Log in to continue to your dashboard.</p>', unsafe_allow_html=True)

            with st.form("login_form"):
                email = st.text_input("Email", key="login_email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    success, message = verify_user(email, password)
                    if success:
                        st.session_state.user_email = email.strip().lower()
                        st.session_state.page = "dashboard"
                        st.session_state.dash_nav = "Chat"
                        st.rerun()
                    else:
                        st.error(message)

            st.markdown("<p style='color:#64748b; margin-top:1.2rem; margin-bottom:0.4rem; font-size:0.95rem;'>Don't have an account?</p>", unsafe_allow_html=True)
            if st.button("Create an account", use_container_width=True):
                st.session_state.page = "signup"
                st.rerun()


def render_signup_page():
    render_navbar(show_features=False)

    if st.button("← Back to Home", key="back_home_signup"):
        st.session_state.page = "home"
        st.rerun()

    with st.container(key="auth_container"):
        with st.container(border=True):
            st.markdown("<h2 style='color:#0f172a; margin-bottom:0.1rem; font-size:1.6rem;'>Create your account</h2>", unsafe_allow_html=True)
            st.markdown('<p style="color:#64748b; margin-bottom:1.2rem; font-size:0.95rem;">Sign up to start analyzing videos.</p>', unsafe_allow_html=True)

            with st.form("signup_form"):
                display_name = st.text_input("What should we call you?", key="signup_display_name", placeholder="e.g. Ayesha")
                email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
                password = st.text_input("Choose a password (min 8 characters)", type="password", key="signup_password")
                confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
                submitted = st.form_submit_button("Sign up", type="primary", use_container_width=True)

            if submitted:
                if not display_name or not email or not password or not confirm:
                    st.error("Please fill in all fields.")
                elif password != confirm:
                    st.error("Passwords do not match.")
                else:
                    success, message = register_user(email, password, display_name)
                    if success:
                        st.session_state.auth_flash_message = f"{message} Please log in to continue."
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        st.error(message)

            st.markdown("<p style='color:#64748b; margin-top:1.2rem; margin-bottom:0.4rem; font-size:0.95rem;'>Already have an account?</p>", unsafe_allow_html=True)
            if st.button("Log in instead", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()