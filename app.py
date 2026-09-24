import streamlit as st

# Bootstrap must run before any app module is imported: it loads .env (so the
# module-level os.getenv calls in core/ still see their values), configures
# logging, and creates the runtime directories. Replaces the load_dotenv()
# call that used to live here.
from config import bootstrap

bootstrap()

# Step 7b: create DB tables if they don't exist yet. init_db() is safe to
# call every time (CREATE TABLE IF NOT EXISTS under the hood) -- this just
# means a fresh install works even if scripts/migrate_json_to_sqlite.py was
# never run (nothing to migrate, but auth/history/chat_sessions still need
# the tables to exist).
from db.session import init_db

init_db()

from ui.styles import load_css
from ui.home_page import render_home_page
from ui.auth_pages import render_login_page, render_signup_page
from ui.dashboard import render_dashboard

st.set_page_config(
    page_title="AI Video Assistant",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_css()

# ---- Session defaults ----
if "page" not in st.session_state:
    st.session_state.page = "home"
if "user_email" not in st.session_state:
    st.session_state.user_email = None

# ---- Guard: dashboard requires login ----
if st.session_state.page == "dashboard" and not st.session_state.user_email:
    st.session_state.page = "login"

# ---- Router ----
if st.session_state.page == "home":
    render_home_page()
elif st.session_state.page == "login":
    render_login_page()
elif st.session_state.page == "signup":
    render_signup_page()
elif st.session_state.page == "dashboard":
    render_dashboard()
else:
    st.session_state.page = "home"
    st.rerun()
