import streamlit as st


def load_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

        :root {
            /* ---- Brand palette (Modern Bright Light Theme) ---- */
            --paper: #F8FAFC;
            --paper-raised: #FFFFFF;
            --ink: #0F172A;
            --slate: #475569;
            --slate-light: #94A3B8;
            --mist: #F1F5F9;
            --hairline: #E2E8F0;

            --cobalt: #2563EB;
            --cobalt-dark: #1D4ED8;
            --cobalt-tint: #EFF6FF;
            --amber: #F59E0B;
            --amber-tint: #FEF3C7;

            /* ---- Back-compat aliases (existing rules throughout the app
                   reference these var names — repointing them at the new
                   palette re-skins the whole app without needing to hunt
                   down every individual rule) ---- */
            --accent: var(--cobalt);
            --accent-dark: var(--cobalt-dark);
            --accent-light: var(--cobalt-tint);

            /* ---- Type ---- */
            --font-display: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-body: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            --font-mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;

            /* ---- Motion ---- */
            --ease: cubic-bezier(0.4, 0, 0.2, 1);
            --transition-fast: 150ms var(--ease);
            --transition: 220ms var(--ease);
        }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after {
                animation-duration: 0.001ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.001ms !important;
                scroll-behavior: auto !important;
            }
        }

        html { font-size: 18px; scroll-behavior: smooth; }
        #MainMenu, footer, header {visibility: hidden;}
        .block-container {padding-top: 1.5rem; max-width: 1120px;}

        html, body, [class*="css"], .stApp, .stMarkdown, .stButton>button,
        input, textarea, select, .stTextInput input, .stSelectbox div {
            font-family: var(--font-body) !important;
        }

        .stApp { background: var(--paper); color: var(--ink); }

        /* ---------- Navbar (home page header) ---------- */
        div[class*="st-key-navbar_wrap"] {
            background: var(--paper-raised);
            border: 1px solid var(--hairline);
            border-radius: 14px;
            padding: 0.6rem 1rem;
            margin-bottom: 2rem;
            box-shadow: 0 1px 3px rgba(20,24,31,0.04);
        }
        .navbar-brand {
            font-family: var(--font-display);
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--ink);
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding-top: 0.4rem;
        }
        .navbar-user {
            text-align: right;
            padding-top: 0.55rem;
            color: var(--ink);
            font-weight: 600;
            font-size: 1rem;
        }
        .navbar-link-wrap {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            padding-top: 0.3rem;
        }
        .navbar-link {
            color: var(--slate);
            font-weight: 600;
            font-size: 0.98rem;
            text-decoration: none;
            padding: 0.5rem 0.8rem;
            border-radius: 8px;
            transition: color var(--transition), background-color var(--transition);
        }
        .navbar-link:hover {
            color: var(--cobalt);
            background: var(--cobalt-tint);
        }

        /* ---------- General text contrast (default — component-specific
           rules further down, e.g. .cta-band h2, correctly override this) ---------- */
        h1, h2, h3, .stMarkdown, .stMarkdown p, label, .stSubheader { color: var(--ink) !important; }
        h1, h2, h3 { font-family: var(--font-display) !important; font-weight: 600 !important; }
        [data-testid="stHeader"] { background: transparent; }
        .stApp, .stApp p, .stApp span, .stApp label { color: #374151; font-size: 1.05rem; }

        /* Any element opted into the display face — headlines, titles */
        .font-display { font-family: var(--font-display) !important; }
        .font-mono { font-family: var(--font-mono) !important; }

        /* Baseline smooth transitions for common interactive elements —
           individual components below layer on richer hover treatments. */
        a, button, .stButton>button, .stTextInput input, .stSelectbox div {
            transition: background-color var(--transition), border-color var(--transition),
                        color var(--transition), box-shadow var(--transition),
                        transform var(--transition-fast) !important;
        }

        /* ---------- Hero ---------- */
        .hero-wrap { text-align: center; padding: 3rem 1rem 2rem 1rem; }
        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: var(--cobalt-tint);
            color: var(--cobalt-dark);
            font-weight: 600;
            font-size: 0.85rem;
            padding: 0.4rem 1rem;
            border-radius: 999px;
            margin-bottom: 1.4rem;
            letter-spacing: 0.02em;
            font-family: var(--font-mono);
        }
        .hero-title {
            font-family: var(--font-display);
            font-size: 3.6rem;
            font-weight: 700;
            color: var(--ink);
            margin-bottom: 1rem;
            line-height: 1.12;
            letter-spacing: -0.01em;
        }
        .hero-title span {
            background: linear-gradient(90deg, var(--cobalt), var(--amber));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .hero-sub {
            color: var(--slate);
            font-size: 1.2rem;
            max-width: 640px;
            margin: 0 auto;
            line-height: 1.65;
        }

        /* ---------- Highlight chips ---------- */
        .highlight-row {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 0.7rem;
            margin: 2rem 0 0.5rem 0;
        }
        .highlight-chip {
            background: var(--paper-raised);
            border: 1px solid var(--hairline);
            color: var(--ink);
            font-size: 0.9rem;
            font-weight: 500;
            padding: 0.55rem 1.05rem;
            border-radius: 999px;
            transition: border-color var(--transition), transform var(--transition-fast);
        }
        .highlight-chip:hover {
            border-color: var(--cobalt);
            transform: translateY(-1px);
        }

        /* ---------- Signature element: timeline scrubber ---------- */
        .scrubber-wrap {
            max-width: 780px;
            margin: 2.6rem auto 0 auto;
            padding: 0 1rem;
        }
        .scrubber-track {
            position: relative;
            height: 3px;
            background: var(--hairline);
            border-radius: 999px;
            margin: 0 6px;
        }
        .scrubber-fill {
            position: absolute;
            top: 0; left: 0;
            height: 100%;
            width: 100%;
            background: linear-gradient(90deg, var(--cobalt), var(--amber));
            border-radius: 999px;
            opacity: 0.35;
        }
        .scrubber-marks {
            position: relative;
            display: flex;
            justify-content: space-between;
        }
        .scrubber-mark {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 1px;
            animation: scrubber-pop 0.5s var(--ease) both;
        }
        .scrubber-mark:nth-child(1) { animation-delay: 0.05s; }
        .scrubber-mark:nth-child(2) { animation-delay: 0.18s; }
        .scrubber-mark:nth-child(3) { animation-delay: 0.31s; }
        .scrubber-mark:nth-child(4) { animation-delay: 0.44s; }
        @keyframes scrubber-pop {
            from { opacity: 0; transform: translateY(6px) scale(0.8); }
            to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        .scrubber-dot {
            width: 11px;
            height: 11px;
            border-radius: 50%;
            background: var(--paper-raised);
            border: 2.5px solid var(--cobalt);
            margin-top: -4.5px;
            transition: transform var(--transition-fast), border-color var(--transition);
        }
        .scrubber-mark:hover .scrubber-dot {
            transform: scale(1.25);
            border-color: var(--amber);
        }
        .scrubber-time {
            font-family: var(--font-mono);
            font-size: 0.78rem;
            font-weight: 600;
            color: var(--ink);
            margin-top: 0.55rem;
            white-space: nowrap;
        }
        .scrubber-label {
            font-size: 0.76rem;
            color: var(--slate);
            margin-top: 0.15rem;
            white-space: nowrap;
        }

        /* ---------- Feature cards ---------- */
        .feature-card {
            background: var(--paper-raised);
            border: 1px solid var(--hairline);
            border-radius: 16px;
            padding: 1.8rem;
            height: 100%;
            box-shadow: 0 1px 2px rgba(20, 24, 31, 0.03);
            transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
        }
        .feature-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 14px 28px rgba(47, 95, 224, 0.12);
            border-color: var(--cobalt);
        }
        .feature-card .icon {
            font-size: 1.6rem;
            margin-bottom: 0.8rem;
            width: 46px;
            height: 46px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 12px;
            background: var(--cobalt-tint);
        }
        .feature-card h4 {
            font-family: var(--font-display);
            color: var(--ink);
            margin: 0 0 0.5rem 0;
            font-size: 1.15rem;
            font-weight: 600;
        }
        .feature-card p { color: var(--slate); font-size: 1rem; margin: 0; line-height: 1.55; }

        /* ---------- Step cards ---------- */
        .step-card {
            background: var(--paper-raised);
            border: 1px solid var(--hairline);
            border-radius: 16px;
            padding: 1.9rem 1.6rem;
            height: 100%;
            text-align: center;
            transition: transform var(--transition), box-shadow var(--transition);
        }
        .step-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 14px 28px rgba(20, 24, 31, 0.08);
        }
        .step-number {
            width: 38px;
            height: 38px;
            line-height: 38px;
            border-radius: 50%;
            background: var(--cobalt);
            color: #ffffff;
            font-family: var(--font-mono);
            font-weight: 600;
            margin: 0 auto 0.9rem auto;
        }
        .step-card h4 {
            font-family: var(--font-display);
            color: var(--ink);
            margin: 0 0 0.5rem 0;
            font-size: 1.1rem;
            font-weight: 600;
        }
        .step-card p { color: var(--slate); font-size: 0.98rem; margin: 0; line-height: 1.55; }

        /* ---------- CTA band ---------- */
        .cta-band {
            background: linear-gradient(135deg, var(--cobalt), var(--cobalt-dark));
            border-radius: 20px;
            padding: 2.8rem 2rem 2.2rem 2rem;
            text-align: center;
            margin: 3rem 0 0.5rem 0;
            position: relative;
            overflow: hidden;
        }
        .cta-band::after {
            content: "";
            position: absolute;
            top: -40%; right: -10%;
            width: 260px; height: 260px;
            background: radial-gradient(circle, rgba(242,169,59,0.35), transparent 70%);
            pointer-events: none;
        }
        .cta-band h2 {
            font-family: var(--font-display);
            color: #ffffff !important;
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            position: relative;
        }
        .cta-band h2 * { color: #ffffff !important; }
        .cta-band p { color: #DCE6FC !important; font-size: 1.05rem; margin: 0; position: relative; }
        .cta-band p * { color: #DCE6FC !important; }

        /* ---------- Section titles ---------- */
        .section-title {
            font-family: var(--font-display);
            color: var(--ink);
            font-weight: 600;
            font-size: 1.9rem;
            margin: 1.2rem 0 1.3rem 0;
        }

        /* ---------- Stats page ---------- */
        .stats-heading {
            font-family: var(--font-display);
            color: var(--ink);
            font-weight: 600;
            font-size: 1.65rem;
            margin: 0.6rem 0 1.4rem 0;
        }
        .stat-card {
            background: var(--paper-raised);
            border: 1px solid var(--hairline);
            border-radius: 14px;
            padding: 1.1rem 1.2rem;
            height: 100%;
            transition: transform var(--transition), box-shadow var(--transition), border-color var(--transition);
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 22px rgba(20, 24, 31, 0.07);
            border-color: var(--cobalt);
        }
        .stat-card-icon { font-size: 1.4rem; margin-bottom: 0.5rem; line-height: 1; }
        .stat-card-value {
            font-size: 1.35rem;
            font-weight: 700;
            color: #111827;
            line-height: 1.25;
            word-break: break-word;
        }
        .stat-card-label {
            font-size: 0.82rem;
            color: #6b7280;
            margin-top: 0.3rem;
        }
        .chart-section-title {
            font-weight: 700;
            font-size: 1.02rem;
            color: #191919;
            margin-bottom: 0.7rem;
        }

        /* ---------- Footer ---------- */
        .footer {
            text-align: center;
            color: #9ca3af;
            font-size: 0.92rem;
            padding: 2.5rem 0 1rem 0;
            border-top: 1px solid var(--hairline);
            margin-top: 3rem;
        }

        /* =====================================================
           SIDEBAR
           ===================================================== */
        section[data-testid="stSidebar"] {
            background: var(--mist);
            border-right: 1px solid var(--hairline);
        }
        section[data-testid="stSidebar"] > div:first-child {
            display: flex;
            flex-direction: column;
            height: 100dvh;
            padding-top: 0 !important;
            position: relative !important;
        }
        div[data-testid="stSidebarHeader"] {
            position: absolute !important;
            top: 0 !important;
            right: 0.75rem !important;
            left: auto !important;
            height: 2.6rem !important;
            min-height: 0 !important;
            margin: 0 !important;
            width: auto !important;
            display: flex !important;
            align-items: center !important;
            z-index: 10 !important;
        }
        div[data-testid="stLogoSpacer"] {
            display: none !important;
        }
        div[data-testid="stSidebarUserContent"] {
            display: flex;
            flex-direction: column;
            flex: 1;
            gap: 0 !important;
            padding-top: 0.45rem !important;
            padding-bottom: 4.75rem !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
            gap: 0.1rem !important;
        }

        /* Brand */
        .app-brand {
            font-family: var(--font-display);
            font-size: 1.4rem;
            font-weight: 700;
            color: var(--ink);
            letter-spacing: -0.01em;
            padding: 0 0 0 0.1rem;
            margin: 0 !important;
            line-height: 1.2;
        }
        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div {
            gap: 0rem !important;
        }
        div[data-testid="stSidebarUserContent"] button {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 0.02rem !important;
            padding-bottom: 0.02rem !important;
            width: 100% !important;
            line-height: 1.3 !important;
        }
        .sidebar-brand-spacer {
            height: 1.3rem !important;
        }
        section[data-testid="stSidebar"] hr.sidebar-hr {
            border: none !important;
            border-top: 1px solid #e5e7eb !important;
            margin: 0 0 0.2rem 0 !important;
        }
        /* Profile block pinned to the true bottom of the sidebar.
           NOTE: a flex-grow spacer div doesn't work here because it sits several
           nested divs below the flex container, and flex-grow only affects a
           DIRECT child of the flex parent. We pin with absolute positioning instead. */
        div[class*="st-key-profile_section"] {
            position: absolute !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            background: var(--mist) !important;
            padding: 0 0.5rem 1rem 0.5rem !important;
            z-index: 5 !important;
        }
        div[class*="st-key-profile_section"] div[data-testid="stPopover"] button {
            padding-left: 0.5rem !important;
        }

        /* Flat, borderless nav buttons (ChatGPT/Claude style) */
        div[data-testid="stSidebarUserContent"] button {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #374151 !important;
            font-weight: 500 !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 0.5rem 0.6rem !important;
            border-radius: 8px !important;
        }
        div[data-testid="stSidebarUserContent"] button:hover {
            background-color: #f0f1f3 !important;
            box-shadow: none !important;
        }
        div[data-testid="stSidebarUserContent"] button[kind="primary"] {
            background-color: #eef2ff !important;
            color: #1e3a8a !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
        }

        /* Section labels / empty states */
        .sidebar-section-label {
            color: #6b7280;
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin: 0.4rem 0 0.8rem 0.2rem;
        }
        .sidebar-empty-note { color: #9ca3af; font-size: 0.9rem; padding: 0.3rem 0.2rem 0.6rem 0.2rem; }

        .sidebar-user-name { font-size: 1.08rem; font-weight: 700; color: #111827; }
        .sidebar-user-email { color: #6b7280; font-size: 0.88rem; }

        /* =====================================================
           MAIN CONTENT
           ===================================================== */

        /* ---------- Inputs ---------- */
        .stTextInput>div>div>input {
            background-color: var(--paper-raised) !important;
            color: var(--ink) !important;
            border: 1px solid #d1d5db !important;
            border-radius: 10px !important;
            font-size: 1.05rem !important;
            padding: 0.6rem 0.8rem !important;
            transition: border-color var(--transition), box-shadow var(--transition) !important;
        }
        /* Password fields have a built-in show/hide icon button overlapping
           the right edge — without extra padding, typed text runs underneath it. */
        .stTextInput input[type="password"] {
            padding-right: 2.75rem !important;
        }
        /* The "Press Enter to..." hint bubble Streamlit shows while typing is a
           separate absolutely-positioned element, unaffected by the input's own
           padding above — it needs its own clearance from the eye icon button. */
        div[data-testid="InputInstructions"] {
            margin-right: 2.5rem !important;
        }
        .stTextInput>div>div>input:focus {
            border-color: var(--cobalt) !important;
            box-shadow: 0 0 0 3px rgba(47,95,224,0.14) !important;
        }
        .stTextInput label, .stSelectbox label {
            color: #374151 !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
        }
        div[data-baseweb="select"] > div {
            background-color: var(--paper-raised) !important;
            color: var(--ink) !important;
            border: 1px solid #d1d5db !important;
            border-radius: 10px !important;
            transition: border-color var(--transition) !important;
        }

        /* Password show/hide icon */
        div[data-testid="stTextInput"] button,
        div[data-testid="stTextInputRootElement"] button {
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            opacity: 1 !important;
        }
        div[data-testid="stTextInput"] button svg,
        div[data-testid="stTextInputRootElement"] button svg {
            fill: #6b7280 !important;
            stroke: #6b7280 !important;
            opacity: 1 !important;
        }
        div[data-testid="stTextInput"] button:hover svg {
            fill: #111827 !important;
            stroke: #111827 !important;
        }

        /* ---------- Auth / bordered card wrapper ---------- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--paper-raised);
            border: 1px solid var(--hairline);
            border-radius: 16px;
            padding: 0.5rem;
            box-shadow: 0 1px 3px rgba(20,24,31,0.05);
        }

        /* ---------- Alerts ---------- */
        div[data-testid="stAlert"] {
            background-color: #ffffff !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 10px !important;
        }
        div[data-testid="stAlert"] p { color: #1f2937 !important; font-size: 1rem !important; }

        /* ---------- Buttons (main content area only) ---------- */
        .stApp button {
            background-color: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #d1d5db !important;
            opacity: 1 !important;
            visibility: visible !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }
        .stApp button:hover {
            background-color: #f3f4f6 !important;
            border-color: var(--accent) !important;
        }
        .stApp button:focus-visible {
            outline: 2px solid var(--accent) !important;
            outline-offset: 1px !important;
        }
        .stApp button[kind="primary"],
        .stApp button[kind="primaryFormSubmit"],
        button[kind="primary"],
        button[kind="primaryFormSubmit"] {
            background-color: var(--accent) !important;
            color: #ffffff !important;
            border: none !important;
            box-shadow: 0 1px 2px rgba(20,24,31,0.06) !important;
        }
        .stApp button[kind="primary"]:hover,
        .stApp button[kind="primaryFormSubmit"]:hover,
        button[kind="primary"]:hover,
        button[kind="primaryFormSubmit"]:hover {
            background-color: var(--accent-dark) !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 16px rgba(47,95,224,0.28) !important;
        }
        .stApp button[kind="primary"]:active,
        .stApp button[kind="primaryFormSubmit"]:active,
        button[kind="primary"]:active,
        button[kind="primaryFormSubmit"]:active {
            transform: translateY(0) !important;
        }
        /* Ensure ALL text inside blue primary buttons is bright white */
        button[kind="primary"] *,
        button[kind="primaryFormSubmit"] *,
        .stApp button[kind="primary"] *,
        .stApp button[kind="primaryFormSubmit"] *,
        div[data-testid="stFormSubmitButton"] button *,
        div[data-testid="stButton"] button[kind="primary"] * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }

        /* ---------- Auth container: form card ----------
        Bigger, centered rectangular card (no side brand panel anymore). */
        div[class*="st-key-auth_container"] {
            max-width: 600px !important;
            margin: 3rem auto 2.5rem auto !important;
            width: 100% !important;
            padding: 0 0.5rem !important;
        }
        div[class*="st-key-auth_container"] div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--paper-raised) !important;
            border: 1px solid var(--hairline) !important;
            border-radius: 16px !important;
            padding: 2.6rem 3rem 2.4rem 3rem !important;
            box-shadow: 0 4px 20px rgba(15, 23, 42, 0.05) !important;
        }

        /* ---------- Auth brand panel (decorative half of the login/signup
           row). Streamlit's own column CSS already stacks this above the
           form on narrow/mobile screens — nothing custom needed for that. */
        .auth-brand-panel {
            max-width: 440px;
            margin: 2.2rem auto 1.5rem auto;
            padding: 0 0.5rem;
        }
        .auth-brand-badge {
            display: inline-flex;
            align-items: center;
            background: var(--cobalt-tint);
            color: var(--cobalt-dark);
            font-weight: 600;
            font-size: 0.85rem;
            padding: 0.35rem 0.9rem;
            border-radius: 999px;
            margin-bottom: 1.1rem;
            font-family: var(--font-mono);
        }
        .auth-brand-title {
            font-family: var(--font-display);
            font-size: 2rem !important;
            font-weight: 700 !important;
            color: var(--ink) !important;
            line-height: 1.2;
            margin-bottom: 0.9rem !important;
        }
        .auth-brand-sub {
            color: var(--slate);
            font-size: 1.02rem;
            line-height: 1.6;
            margin-bottom: 1.4rem;
        }
        .auth-brand-list {
            list-style: none;
            padding: 0;
            margin: 0;
            display: flex;
            flex-direction: column;
            gap: 0.7rem;
        }
        .auth-brand-list li {
            color: var(--ink);
            font-weight: 500;
            font-size: 0.98rem;
            background: var(--paper-raised);
            border: 1px solid var(--hairline);
            border-radius: 10px;
            padding: 0.65rem 0.9rem;
        }
        @media (max-width: 640px) {
            .auth-brand-panel { text-align: center; margin-top: 0.5rem; }
            .auth-brand-title { font-size: 1.6rem !important; }
            .auth-brand-list { align-items: center; }
            .auth-brand-list li { width: 100%; max-width: 340px; }
        }

        /* ---------- Results Tab Styling ---------- */
        .results-title {
            font-family: var(--font-display);
            font-size: 1.55rem;
            font-weight: 700;
            color: var(--ink);
            margin: 0.2rem 0 0.3rem 0;
            line-height: 1.3;
        }
        .results-meta {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin-bottom: 0.5rem;
        }
        .badge-pill {
            display: inline-flex;
            align-items: center;
            font-size: 0.82rem;
            font-weight: 600;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
        }
        .badge-primary {
            background: var(--cobalt-tint);
            color: var(--cobalt-dark);
            border: 1px solid rgba(37,99,235,0.15);
        }
        .source-link {
            color: var(--cobalt);
            font-size: 0.88rem;
            font-weight: 500;
            text-decoration: none;
        }
        .source-link:hover { text-decoration: underline; }
        .results-empty-container {
            text-align: center;
            background: var(--paper-raised);
            border: 1px dashed var(--hairline);
            border-radius: 16px;
            padding: 2.8rem 1.5rem;
            margin: 1.2rem 0;
        }

        /* Extracted video-frame images in chat */
        .chat-bubble.assistant.chat-image-bubble { max-width: 340px !important; }
        .chat-frame-img {
            width: 100%;
            border-radius: 12px;
            border: 1px solid var(--hairline);
            display: block;
        }
        .chat-frame-caption {
            font-family: var(--font-mono);
            font-size: 0.85rem;
            color: var(--slate);
            margin-top: 0.5rem;
        }

        /* Top-right language pill */
        div[data-testid="stSelectbox"] > div > div {
            border-radius: 999px !important;
            border-color: #e5e7eb !important;
        }

        /* Chat scroll area: no border/box, just an open canvas like ChatGPT */
        div[class*="st-key-chat_container"] > div[data-testid="stVerticalBlockBorderWrapper"] {
            border: none !important;
            background: transparent !important;
        }

        /* Fixed bottom bar (holds the chat input) previously had a hardcoded
           white background that clashed with the new paper background above it. */
        div[data-testid="stBottomBlockContainer"],
        div[data-testid="stBottom"] {
            background: var(--paper) !important;
            border-top: 1px solid var(--hairline);
        }

        .stChatInput textarea, .stChatInput input {
            background-color: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #d1d5db !important;
            border-radius: 10px !important;
            font-size: 1.05rem !important;
        }

        /* ---------- Tabs ---------- */
        button[data-baseweb="tab"] { color: #6b7280 !important; font-weight: 600 !important; font-size: 1rem !important; }
        button[data-baseweb="tab"][aria-selected="true"] {
            color: var(--accent) !important;
            border-bottom-color: var(--accent) !important;
        }

        /* ---------- Metrics ---------- */
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 0.8rem;
        }
        div[data-testid="stMetricLabel"] { color: #6b7280 !important; }
        div[data-testid="stMetricValue"] { color: #111827 !important; }

        /* ---------- History cards ---------- */
        .history-title { font-size: 1.15rem; font-weight: 700; color: #0f172a; }
        .history-meta { color: #6b7280; font-size: 0.9rem; margin: 0.3rem 0; }
        .history-meta a { color: var(--accent); text-decoration: none; }
        .history-snippet { color: #374151; font-size: 1rem; margin-top: 0.4rem; line-height: 1.5; }

        /* ---------- Responsive ---------- */
        @media (max-width: 768px) {
            .hero-title { font-size: 2.1rem !important; }
            .hero-sub { font-size: 1.05rem !important; }
            .feature-card, .step-card { padding: 1.2rem !important; }
            .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
            .scrubber-track { display: none; }
            .scrubber-marks {
                flex-wrap: wrap;
                justify-content: center;
                row-gap: 1.4rem;
                column-gap: 2.2rem;
            }
            div[class*="st-key-auth_container"] div[data-testid="stVerticalBlockBorderWrapper"] {
                padding: 1.6rem 1.4rem !important;
            }
            .scrubber-mark { width: auto !important; }
            .scrubber-dot { margin-top: 0 !important; }
            .scrubber-wrap { margin-top: 2rem; }
            .stat-card { padding: 0.9rem !important; }
        }
        @media (max-width: 480px) {
            .hero-title { font-size: 1.7rem !important; }
            .hero-badge { font-size: 0.75rem !important; padding: 0.35rem 0.8rem !important; }
        }
        /* ---------- Sidebar button override (must be last: fixes hover/primary conflicts) ---------- */
        div[data-testid="stSidebarUserContent"] button,
        div[data-testid="stSidebarUserContent"] button[kind="secondary"] {
            background-color: transparent !important;
            border: none !important;
            color: #374151 !important;
        }
        div[data-testid="stSidebarUserContent"] button:hover {
            background-color: #eceef1 !important;
            border: none !important;
        }
                div[data-testid="stSidebarUserContent"] button[kind="primary"] {
            background-color: #eef2ff !important;
            color: #1e3a8a !important;
            border: none !important;
        }
        div[data-testid="stSidebarUserContent"] button[kind="primary"] *,
        div[data-testid="stSidebarUserContent"] div[data-testid="stButton"] button[kind="primary"] * {
            color: #1e3a8a !important;
            -webkit-text-fill-color: #1e3a8a !important;
        }
        div[data-testid="stSidebarUserContent"] button[kind="primary"]:hover {
            background-color: #e0e7ff !important;
        }
                /* ---------- Nuke any leftover pseudo-element icons in sidebar ---------- */
        div[data-testid="stSidebarUserContent"] button::before,
        div[data-testid="stSidebarUserContent"] button::after {
            content: none !important;
            display: none !important;
        }

        /* ---------- Fix icon/text spacing so it aligns left properly ---------- */
        div[data-testid="stSidebarUserContent"] button {
            gap: 0.5rem !important;
        }
        div[data-testid="stSidebarUserContent"] button p {
            margin: 0 !important;
        }
        div[data-testid="stSidebarUserContent"] button span[data-testid="stIconMaterial"] {
            margin: 0 !important;
        }
        div[data-testid="stSidebarUserContent"] button > div {
            justify-content: flex-start !important;
            width: 100% !important;
        }
        div[class*="st-key-nav_block"] .stButton {
            margin-top: 0rem !important;
            margin-bottom: 0rem !important;
        }
        /* Recent chats: 3-dot popover trigger */
        section[data-testid="stSidebar"] div[data-testid="stPopover"] button {
            padding: 0.2rem 0.4rem !important;
            font-size: 1.1rem !important;
            line-height: 1 !important;
        }
        /* No horizontal scroll in Recent chats */
        section[data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {
            overflow-x: hidden !important;
        }

        /* Chat titles: single line, no wrap */
        section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] button p {
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }

        /* Hide dropdown caret on popover triggers (profile button) */
        section[data-testid="stSidebar"] div[data-testid="stPopover"] button svg {
            display: none !important;
        }
        /* ---------- Tighten vertical spacing between sidebar elements ---------- */
        section[data-testid="stSidebar"] div[data-testid="element-container"] {
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
        }
        div[class*="st-key-nav_block"] .stButton {
            margin: 0 !important;
        }
        div[class*="st-key-nav_block"] div[data-testid="stElementContainer"],
        div[class*="st-key-nav_block"] div[data-testid="element-container"] {
            margin: 0 !important;
            padding: 0 !important;
        }
        div[data-testid="stSidebarUserContent"] button {
            min-height: 0 !important;
            height: auto !important;
            line-height: 1.4 !important;
            padding-top: 0.3rem !important;
            padding-bottom: 0.3rem !important;
        }
        div[class*="st-key-recent_box"] button {
            padding-top: 0.15rem !important;
            padding-bottom: 0.15rem !important;
        }
        /* ---------- Profile row ---------- */
        .profile-hr {
            margin-top: 0 !important;
            margin-bottom: 0.6rem !important;
        }
        .profile-popup-email {
            color: #6b7280;
            font-size: 0.85rem;
            padding: 0.2rem 0;
        }
        /* ---------- Hard reset: undo ALL our CSS on the sidebar toggle button ---------- */
        button[data-testid="stSidebarCollapseButton"],
        button[data-testid="collapsedControl"] {
        background-color: #ffffff !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 8px !important;
    }
    </style>
    """, unsafe_allow_html=True)