from utils.chat_sessions import upsert_session
import streamlit as st
import streamlit.components.v1 as components
import uuid
import re
from datetime import datetime
from ui.sidebar import render_sidebar
import pandas as pd
from main import run_pipeline
from core.rag_engine import ask_question
from core.quiz_generator import generate_quiz
from core.notes_generator import generate_notes, build_notes_pdf
from utils.history_manager import (
    add_entry,
    get_history,
    get_stats,
    get_activity_dataframe,
    get_language_dataframe,
    get_category_dataframe,
)

SOURCE_EXTENSIONS = (
    ".mp4",
    ".mp3",
    ".wav",
    ".mkv",
    ".mov",
    ".avi",
    ".m4a",
    ".webm",
    ".flac",
)


def _looks_like_source(text: str) -> bool:
    t = text.strip().strip("\"'").strip().lower()

    if t.startswith("http://") or t.startswith("https://"):
        return True

    if t.endswith(SOURCE_EXTENSIONS):
        return True

    return False


_TIMESTAMP_RE = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")
_CITED_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]")

_FRAME_INTENT_PHRASES = (
    "image", "picture", "photo", "screenshot", "screen shot", "screen",
    "slide", "frame", "look like", "shown", "displayed", "what's on",
    "what is on", "show me", "what does it show", "what do i see", "visual",
)


def _timestamp_match_to_seconds(match) -> float:
    parts = [int(p) for p in match.groups() if p is not None]
    if len(parts) == 3:
        h, m, s = parts
    else:
        h = 0
        m, s = parts
    return float(h * 3600 + m * 60 + s)


def _format_seconds(total_seconds: float) -> str:
    total_seconds = int(total_seconds)
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _parse_mmss(text: str) -> float:
    parts = [int(p) for p in text.split(":")]
    if len(parts) == 3:
        h, m, s = parts
    else:
        h = 0
        m, s = parts
    return float(h * 3600 + m * 60 + s)


def _last_cited_timestamp(chat_history: list):
    for msg in reversed(chat_history):
        if msg.get("role") == "assistant" and msg.get("type") != "image":
            cited = _CITED_TIMESTAMP_RE.search(msg.get("content", ""))
            if cited:
                return _parse_mmss(cited.group(1))
    return None


_FRAME_STOPWORDS = {
    "extract", "frame", "image", "picture", "photo", "screenshot", "screen",
    "shot", "slide", "look", "like", "shown", "displayed", "show", "me",
    "the", "a", "an", "of", "at", "in", "on", "was", "is", "were", "please",
    "can", "you", "to", "what's", "whats", "what", "that", "this", "it",
    "there", "here", "and", "with",
}


def _classify_frame_request(message: str, chat_history: list):
    """Classifies a message as a video-frame request, returning one of:
       ("direct", seconds)   - an explicit timestamp is stated in this message
       ("history", None)     - a pure pronoun follow-up ("show me that"),
                                caller should reuse the last [MM:SS] the
                                assistant already cited
       ("lookup", message)   - describes NEW content ("where the biryani was
                                shown") with no timestamp anywhere yet —
                                caller must ask the RAG chain first to find
                                when that content appears, THEN extract
       None                  - not a frame request at all
    """
    lower = message.lower()
    has_frame_intent = any(phrase in lower for phrase in _FRAME_INTENT_PHRASES)
    if not has_frame_intent:
        return None

    direct_match = _TIMESTAMP_RE.search(message)
    if direct_match:
        return ("direct", _timestamp_match_to_seconds(direct_match))

    # Strip frame-intent phrasing and common stop/referential words — if
    # meaningful content words remain (e.g. "mutton biryani", "Mo kappa
    # chino"), this describes something new that needs a fresh lookup rather
    # than reusing whatever was last cited.
    words = re.findall(r"[a-z']+", lower)
    meaningful = [w for w in words if w not in _FRAME_STOPWORDS]

    if len(meaningful) >= 1:
        return ("lookup", message)

    return ("history", None)


_QUIZ_INTENT_PHRASES = (
    "quiz", "test my knowledge", "test me on", "mcq", "multiple choice",
    "questions on this video", "questions about this video",
)


def _is_quiz_request(message: str) -> bool:
    lower = message.lower()
    return any(phrase in lower for phrase in _QUIZ_INTENT_PHRASES)


_NOTES_INTENT_PHRASES = (
    "generate notes", "make notes", "take notes", "give me notes",
    "notes from this video", "notes on this video", "notes about this video",
    "study notes",
)


def _is_notes_request(message: str) -> bool:
    lower = message.lower()
    return any(phrase in lower for phrase in _NOTES_INTENT_PHRASES)


def _generate_and_append_quiz(num_questions: int):
    """Called when the user clicks one of the 5/10/15/20 quiz-size buttons.
    Appends the user's choice + the generated quiz (or an error message) to
    chat_history, then saves the session — mirrors the pattern used for
    every other chat_history append in this file.
    """
    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": f"{num_questions} questions",
            "time": datetime.now().strftime("%I:%M %p"),
        }
    )

    try:
        content_for_quiz = (
            st.session_state.result.get("transcript")
            or st.session_state.result.get("summary", "")
        )
        with st.spinner(f"Writing a {num_questions}-question quiz..."):
            questions = generate_quiz(content_for_quiz, num_questions)

        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "type": "quiz",
                "quiz_id": str(uuid.uuid4()),
                "questions": questions,
                "time": datetime.now().strftime("%I:%M %p"),
            }
        )
    except Exception as e:
        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": f"Sorry, I couldn't generate the quiz: {e}",
                "time": datetime.now().strftime("%I:%M %p"),
            }
        )

    upsert_session(
        st.session_state.user_email,
        st.session_state.current_session_id,
        st.session_state.chat_history,
        st.session_state.result,
    )


def _render_frame_image_html(msg: dict) -> str:
    """Base64-embeds the extracted frame so it renders inline within the
    normal chat bubble styling. Chat history only stores the file PATH (kept
    lean for JSON storage) — the image itself is read and encoded fresh each
    render, so if the underlying file is ever missing this degrades to a
    friendly message instead of a broken image icon.
    """
    import base64

    image_path = msg.get("image_path", "")
    caption = msg.get("caption", "")

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return (
            f'<img src="data:image/jpeg;base64,{b64}" class="chat-frame-img" />'
            f'<div class="chat-text chat-frame-caption">{caption}</div>'
        )
    except (FileNotFoundError, OSError):
        return (
            '<div class="chat-text">⚠️ That frame is no longer available '
            f"({caption}).</div>"
        )


STAGE_LABELS = {
    "downloading": "Downloading audio",
    "processing_audio": "Processing audio",
    "loading_whisper": "Loading Whisper model",
    "transcribing": "Transcribing",
    "summarizing": "Summarizing",
    "extracting": "Extracting information",
    "building_rag": "Building knowledge base",
    "completed": "Completed",
}


def _run_pipeline_with_status(source: str, language: str):
    status_box = st.status("Starting analysis...", expanded=True)

    def on_progress(stage, message):
        label = STAGE_LABELS.get(stage, stage)
        status_box.update(label=f"{label}...")
        status_box.write(message)

    try:
        result = run_pipeline(
            source,
            language,
            on_progress=on_progress,
        )

        status_box.update(
            label="Analysis complete",
            state="complete",
            expanded=False,
        )

        return result, None

    except Exception as e:
        status_box.update(
            label="Analysis failed",
            state="error",
            expanded=True,
        )

        status_box.write(f"Error: {e}")

        return None, str(e)


def _format_export_text(result: dict) -> str:
    title = result.get("title", "Video Analysis")
    category = result.get("category", "General")
    source = result.get("source", "N/A")
    summary = result.get("summary", "No summary available.")
    action_items = result.get("action_items", "No action items extracted.")
    decisions = result.get("key_decisions", "No key decisions extracted.")
    questions = result.get("open_questions", "No open questions extracted.")
    transcript = result.get("transcript", "")

    return (
        f"VIDEO ANALYSIS REPORT\n"
        f"Title: {title}\n"
        f"Category: {category}\n"
        f"Source: {source}\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'='*60}\n\n"
        f"📋 SUMMARY\n{summary}\n\n"
        f"{'='*60}\n\n"
        f"✅ ACTION ITEMS\n{action_items}\n\n"
        f"{'='*60}\n\n"
        f"🔑 KEY DECISIONS\n{decisions}\n\n"
        f"{'='*60}\n\n"
        f"❓ OPEN QUESTIONS\n{questions}\n\n"
        f"{'='*60}\n\n"
        f"📝 TRANSCRIPT\n{transcript}\n"
    )


def render_dashboard():

    if "_dash_nav_redirect" in st.session_state:
        st.session_state.dash_nav = st.session_state.pop(
            "_dash_nav_redirect"
        )

    render_sidebar()

    if "result" not in st.session_state:
        st.session_state.result = None

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "dash_nav" not in st.session_state:
        st.session_state.dash_nav = "Chat"

    if "chat_language" not in st.session_state:
        st.session_state.chat_language = "english"

    email = st.session_state.user_email
    nav = st.session_state.dash_nav

    if nav != "Chat":
        st.markdown(
            '<div class="section-title">Dashboard</div>',
            unsafe_allow_html=True,
        )

    # ---- Chat (also handles first-time analysis, no separate Analyze page) ----
    if nav == "Chat":

        result = st.session_state.result

        top_l, top_r = st.columns([5, 1])
        with top_l:
            if result:
                st.markdown(
                    f'<div class="chat-title">{result["title"]}</div>',
                    unsafe_allow_html=True,
                )
        with top_r:
            st.selectbox(
                "Transcription language",
                ["english", "hinglish"],
                key="chat_language",
                label_visibility="collapsed",
            )

        chat_container = st.container(
            height=560,
            border=False,
            key="chat_container",
        )

        with chat_container:

            for msg in st.session_state.chat_history:

                role_class = (
                    "user"
                    if msg["role"] == "user"
                    else "assistant"
                )

                if msg.get("type") == "image":
                    image_html = _render_frame_image_html(msg)
                    st.markdown(
                        f'<div class="chat-row {role_class}">'
                        f'<div class="chat-bubble {role_class} chat-image-bubble">'
                        f"{image_html}"
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

                elif msg.get("type") == "quiz_count_prompt":
                    st.markdown(
                        f'<div class="chat-row {role_class}">'
                        f'<div class="chat-bubble {role_class}">'
                        f'<div class="chat-text">{msg["content"]}</div>'
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )
                    # Only show the picker while this is still the latest
                    # message — once the user picks a count and a reply is
                    # appended, this prompt is no longer "live".
                    if msg is st.session_state.chat_history[-1]:
                        count_cols = st.columns(4)
                        for i, n in enumerate([5, 10, 15, 20]):
                            with count_cols[i]:
                                if st.button(
                                    str(n),
                                    key=f"quiz_count_{msg['prompt_id']}_{n}",
                                    use_container_width=True,
                                ):
                                    _generate_and_append_quiz(n)
                                    st.rerun()

                elif msg.get("type") == "quiz":
                    quiz_id = msg["quiz_id"]
                    questions = msg["questions"]
                    submissions = st.session_state.setdefault("quiz_submissions", {})
                    state = submissions.setdefault(
                        quiz_id, {"answers": [None] * len(questions), "submitted": False}
                    )

                    st.markdown(
                        f'<div class="chat-row {role_class}">'
                        f'<div class="chat-bubble {role_class}">'
                        f'<div class="chat-text">📝 <strong>Quiz — {len(questions)} questions</strong></div>'
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

                    with st.container(border=True):
                        for qi, q in enumerate(questions):
                            st.markdown(f"**{qi + 1}. {q['question']}**")
                            selected = st.radio(
                                "Choose one",
                                options=list(range(len(q["options"]))),
                                format_func=lambda idx, opts=q["options"]: opts[idx],
                                key=f"quiz_{quiz_id}_{qi}",
                                index=state["answers"][qi],
                                disabled=state["submitted"],
                                label_visibility="collapsed",
                            )
                            state["answers"][qi] = selected

                            if state["submitted"]:
                                correct_idx = q["correct_index"]
                                if selected == correct_idx:
                                    st.success(f"✅ Correct — {q['options'][correct_idx]}")
                                else:
                                    chosen_text = (
                                        q["options"][selected] if selected is not None else "No answer"
                                    )
                                    st.error(
                                        f"❌ You chose: {chosen_text}  \n"
                                        f"Correct answer: {q['options'][correct_idx]}"
                                    )
                            st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

                        if not state["submitted"]:
                            if st.button("Submit Quiz", key=f"submit_{quiz_id}", type="primary"):
                                state["submitted"] = True
                                st.rerun()
                        else:
                            score = sum(
                                1 for qi, q in enumerate(questions)
                                if state["answers"][qi] == q["correct_index"]
                            )
                            st.markdown(f"**Score: {score} / {len(questions)}**")

                elif msg.get("type") == "notes":
                    notes = msg["notes"]
                    video_title = msg.get("video_title", "")

                    st.markdown(
                        f'<div class="chat-row {role_class}">'
                        f'<div class="chat-bubble {role_class}">'
                        f'<div class="chat-text">🗒️ <strong>Notes — {notes.get("title", "Video Notes")}</strong></div>'
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

                    with st.container(border=True):
                        for section in notes.get("sections", []):
                            st.markdown(f"**{section['heading']}**")
                            for bullet in section["bullets"]:
                                st.markdown(f"- {bullet}")
                            st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

                        pdf_bytes = build_notes_pdf(notes, video_title)
                        clean_filename = re.sub(
                            r'[^a-zA-Z0-9_-]', '_',
                            notes.get("title") or video_title or "video_notes"
                        )[:40]
                        st.download_button(
                            "📥 Download Notes (PDF)",
                            data=pdf_bytes,
                            file_name=f"{clean_filename}.pdf",
                            mime="application/pdf",
                            key=f"download_notes_{msg['notes_id']}",
                            use_container_width=True,
                        )

                else:
                    st.markdown(
                        f'<div class="chat-row {role_class}">'
                        f'<div class="chat-bubble {role_class}">'
                        f'<div class="chat-text">{msg["content"]}</div>'
                        f"</div></div>",
                        unsafe_allow_html=True,
                    )

        # Auto-scroll the chat panel to the bottom so the latest message /
        # "Thinking..." indicator is visible without the user manually scrolling.
        components.html(
            """
            <script>
                (function() {
                    const doc = window.parent.document;
                    const box = doc.querySelector('div[class*="st-key-chat_container"]');
                    if (box) { box.scrollTop = box.scrollHeight; }
                })();
            </script>
            """,
            height=0,
        )

        placeholder = (
            "Paste a YouTube link / file path, or ask a question..."
            if not result
            else "Ask a question about this video, or paste a new link to analyze..."
        )

        message = st.chat_input(placeholder)

        if message:

            frame_request = _classify_frame_request(message, st.session_state.chat_history)

            st.session_state.chat_history.append(
                {
                    "role": "user",
                    "content": message,
                    "time": datetime.now().strftime("%I:%M %p"),
                }
            )

            # Scroll the page down to where the processing indicator (status
            # box / "Thinking..." spinner) is about to appear, so the user
            # doesn't have to manually scroll to see that something is happening.
            st.markdown('<div id="chat-bottom-anchor"></div>', unsafe_allow_html=True)
            components.html(
                """
                <script>
                    const doc = window.parent.document;
                    const anchor = doc.getElementById('chat-bottom-anchor');
                    if (anchor) { anchor.scrollIntoView({behavior: 'instant', block: 'end'}); }
                </script>
                """,
                height=0,
            )

            # ---- User entered a video URL/file path ----
            clean_source = message.strip().strip("\"'").strip()
            if _looks_like_source(clean_source):

                # Pasting a new video link always starts a fresh conversation.
                # The previous conversation is already saved in Recent — it's
                # been kept continuously up to date (see the upsert_session
                # call below), so we just need a new id for the fresh chat.
                st.session_state.current_session_id = str(uuid.uuid4())

                st.session_state.chat_history = [
                    {
                        "role": "user",
                        "content": message,
                        "time": datetime.now().strftime("%I:%M %p"),
                    }
                ]
                st.session_state.result = None

                new_result, error = _run_pipeline_with_status(
                    clean_source,
                    st.session_state.chat_language,
                )

                if error:

                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": (
                                f"Something went wrong analyzing that: {error}"
                            ),
                            "time": datetime.now().strftime("%I:%M %p"),
                        }
                    )

                else:

                    st.session_state.result = new_result

                    add_entry(
                        email,
                        new_result["title"],
                        clean_source,
                        new_result["summary"],
                        st.session_state.chat_language,
                        new_result["category"],
                    )

                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": (
                                f"Done! I've analyzed **{new_result['title']}**. "
                                "Ask me anything about it, or check the Results tab."
                            ),
                            "time": datetime.now().strftime("%I:%M %p"),
                        }
                    )

            # ---- User asked a question before analyzing a video ----
            elif not st.session_state.result:

                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": (
                            "I don't have a video to talk about yet — "
                            "paste a YouTube link or a local file path first."
                        ),
                        "time": datetime.now().strftime("%I:%M %p"),
                    }
                )

            # ---- User asked for a video frame ----
            elif frame_request is not None:
                request_kind, request_payload = frame_request
                try:
                    if request_kind == "direct":
                        timestamp_seconds = request_payload

                    elif request_kind == "history":
                        timestamp_seconds = _last_cited_timestamp(st.session_state.chat_history)
                        if timestamp_seconds is None:
                            raise RuntimeError(
                                "I don't have a specific moment to go off yet — "
                                "try naming what you want to see, or a timestamp "
                                "like 'show me 2:30'."
                            )

                    else:  # "lookup" — describes new content, find it first
                        if not st.session_state.result.get("rag_chain"):
                            with st.spinner("Preparing this video's knowledge base..."):
                                from core.rag_engine import build_rag_chain
                                st.session_state.result["rag_chain"] = build_rag_chain(
                                    st.session_state.result["transcript"],
                                    st.session_state.result.get("summary", ""),
                                    st.session_state.result.get("segments"),
                                )

                        with st.spinner("Finding when that was shown..."):
                            lookup_answer = ask_question(
                                st.session_state.result["rag_chain"],
                                request_payload,
                            )

                        cited = _CITED_TIMESTAMP_RE.search(lookup_answer)
                        if not cited:
                            raise RuntimeError(
                                "I couldn't find when that was shown in the video. "
                                f"Here's what I found instead: {lookup_answer}"
                            )
                        timestamp_seconds = _parse_mmss(cited.group(1))

                    with st.spinner("Grabbing that frame from the video..."):
                        from core.frame_extractor import extract_frame
                        frame_path = extract_frame(
                            st.session_state.result.get("source", ""),
                            timestamp_seconds,
                        )
                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "type": "image",
                            "image_path": frame_path,
                            "caption": f"Frame at {_format_seconds(timestamp_seconds)}",
                            "time": datetime.now().strftime("%I:%M %p"),
                        }
                    )
                except Exception as e:
                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": f"I couldn't grab that frame: {e}",
                            "time": datetime.now().strftime("%I:%M %p"),
                        }
                    )

            # ---- User asked for a quiz ----
            elif _is_quiz_request(message):
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "type": "quiz_count_prompt",
                        "prompt_id": str(uuid.uuid4()),
                        "content": "Sure! How many questions would you like?",
                        "time": datetime.now().strftime("%I:%M %p"),
                    }
                )

            # ---- User asked for notes ----
            elif _is_notes_request(message):
                try:
                    content_for_notes = (
                        st.session_state.result.get("transcript")
                        or st.session_state.result.get("summary", "")
                    )
                    with st.spinner("Generating notes..."):
                        notes = generate_notes(content_for_notes)

                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "type": "notes",
                            "notes_id": str(uuid.uuid4()),
                            "notes": notes,
                            "video_title": st.session_state.result.get("title", ""),
                            "time": datetime.now().strftime("%I:%M %p"),
                        }
                    )
                except Exception as e:
                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": f"Sorry, I couldn't generate notes: {e}",
                            "time": datetime.now().strftime("%I:%M %p"),
                        }
                    )

            else:
                try:
                    if not st.session_state.result.get("rag_chain"):
                        with st.spinner("Preparing this video's knowledge base..."):
                            from core.rag_engine import build_rag_chain
                            rag_chain = build_rag_chain(
                                st.session_state.result["transcript"],
                                st.session_state.result.get("summary", ""),
                                st.session_state.result.get("segments"),
                            )
                            st.session_state.result["rag_chain"] = rag_chain

                    with st.spinner("Thinking..."):
                        answer = ask_question(
                            st.session_state.result["rag_chain"],
                            message,
                        )
                except Exception as e:
                    answer = (
                        f"Sorry, I couldn't process that question: {e}"
                    )
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": answer,
                        "time": datetime.now().strftime("%I:%M %p"),
                    }
                )

            # Keep the active conversation continuously saved in Recent,
            # updated in place, instead of only saving when New Chat is clicked.
            upsert_session(
                email,
                st.session_state.current_session_id,
                st.session_state.chat_history,
                st.session_state.result,
            )
            st.rerun()

    # ---- Results ----
    elif nav == "Results":

        if not st.session_state.result:

            st.markdown(
                """
                <div class="results-empty-container">
                    <div style="font-size:2.8rem; margin-bottom:0.8rem;">📋</div>
                    <h3 style="color:#0f172a; margin-bottom:0.4rem;">No Active Analysis Yet</h3>
                    <p style="color:#64748b; max-width:460px; margin:0 auto 1.4rem auto; font-size:1rem; line-height:1.5;">
                        Paste a YouTube link or local video file in <strong>Chat</strong> to generate a complete summary, action items, key decisions, and searchable transcript.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            _, c_btn, _ = st.columns([1, 1, 1])
            with c_btn:
                if st.button("Go to Chat", type="primary", use_container_width=True):
                    st.session_state.dash_nav = "Chat"
                    st.rerun()

        else:

            r = st.session_state.result

            top_col, btn_col = st.columns([3.6, 1.4])
            with top_col:
                st.markdown(f"<h2 class='results-title'>{r.get('title', 'Video Analysis')}</h2>", unsafe_allow_html=True)
                category = r.get("category", "Other")
                source = r.get("source", "")
                badges = f"<span class='badge-pill badge-primary'>🏷️ {category}</span>"
                if source.startswith("http"):
                    badges += f" &nbsp; <a href='{source}' target='_blank' class='source-link'>🔗 Open Source Video ↗</a>"
                st.markdown(f"<div class='results-meta'>{badges}</div>", unsafe_allow_html=True)

            with btn_col:
                export_text = _format_export_text(r)
                clean_filename = re.sub(r'[^a-zA-Z0-9_-]', '_', r.get('title', 'video_analysis'))[:35]
                st.download_button(
                    label="📥 Export Insights (TXT)",
                    data=export_text,
                    file_name=f"{clean_filename}_insights.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
                if st.button("💬 Ask in Chat", use_container_width=True):
                    st.session_state.dash_nav = "Chat"
                    st.rerun()

            st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

            t1, t2, t3, t4, t5 = st.tabs(
                [
                    "📋 Summary",
                    "✅ Action Items",
                    "🔑 Key Decisions",
                    "❓ Open Questions",
                    "📝 Transcript",
                ]
            )

            with t1:
                with st.container(border=True):
                    st.markdown(r.get("summary", "No summary available."))

            with t2:
                with st.container(border=True):
                    st.markdown(r.get("action_items", "No action items extracted."))

            with t3:
                with st.container(border=True):
                    st.markdown(r.get("key_decisions", "No key decisions extracted."))

            with t4:
                with st.container(border=True):
                    st.markdown(r.get("open_questions", "No open questions extracted."))

            with t5:
                with st.container(border=True):
                    transcript_text = r.get("transcript", "")
                    st.caption(f"Length: {len(transcript_text):,} characters")
                    st.markdown(transcript_text if transcript_text else "No transcript available.")

    # ---- Stats ----
        # ---- Stats ----
    elif nav == "Stats":
        st.markdown(
            '<div class="stats-heading">Your statistics</div>',
            unsafe_allow_html=True,
        )

        import plotly.express as px

        stats = get_stats(email)
        history = get_history(email)
        cat_df = get_category_dataframe(email)
        lang_df = get_language_dataframe(email)
        activity_df = get_activity_dataframe(email)

        if not history:
            st.info("No analysis data yet — analyze a few videos to see your stats here.")

        else:
            COLOR_SEQUENCE = [
                "#1e3a8a", "#2563eb", "#60a5fa", "#0ea5e9",
                "#14b8a6", "#f59e0b", "#f97316", "#6b7280",
            ]

            top_category = (
                cat_df.loc[cat_df["count"].idxmax(), "category"]
                if not cat_df.empty else "—"
            )

            weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weekday_df = None
            most_active_day = "—"
            if not activity_df.empty:
                weekday_df = activity_df.copy()
                weekday_df["weekday"] = pd.to_datetime(weekday_df["date"]).dt.day_name()
                weekday_df = (
                    weekday_df.groupby("weekday")["count"].sum()
                    .reindex(weekday_order)
                    .fillna(0)
                    .reset_index()
                )
                most_active_day = weekday_df.loc[weekday_df["count"].idxmax(), "weekday"]

            # ---- Stat cards ----
            cards = [
                ("🎬", str(stats["total_analyzed"]), "Total videos analyzed"),
                ("🏷️", top_category, "Most-watched category"),
                ("📅", most_active_day, "Most active day"),
                ("🕐", stats["last_activity"], "Last activity"),
            ]

            card_cols = st.columns(4)
            for col, (icon, value, label) in zip(card_cols, cards):
                with col:
                    st.markdown(
                        f"""
                        <div class="stat-card">
                            <div class="stat-card-icon">{icon}</div>
                            <div class="stat-card-value">{value}</div>
                            <div class="stat-card-label">{label}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.markdown("<div style='height:1.8rem;'></div>", unsafe_allow_html=True)

            # ---- Category breakdown ----
            if not cat_df.empty:
                st.markdown('<div class="chart-section-title">Video categories</div>', unsafe_allow_html=True)

                pie_col, bar_col = st.columns(2)

                with pie_col:
                    fig_pie = px.pie(
                        cat_df,
                        names="category",
                        values="count",
                        hole=0.55,
                        color="category",
                        color_discrete_sequence=COLOR_SEQUENCE,
                    )
                    fig_pie.update_traces(textinfo="percent+label", textfont_size=11)
                    fig_pie.update_layout(
                        showlegend=False,
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=280,
                        font=dict(family="Inter, sans-serif", color="#374151"),
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)

                with bar_col:
                    fig_bar = px.bar(
                        cat_df.sort_values("count", ascending=True),
                        x="count",
                        y="category",
                        orientation="h",
                        color="category",
                        color_discrete_sequence=COLOR_SEQUENCE,
                    )
                    fig_bar.update_layout(
                        showlegend=False,
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=280,
                        xaxis_title="Videos",
                        yaxis_title="",
                        font=dict(family="Inter, sans-serif", color="#374151"),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                st.markdown("<div style='height:1.8rem;'></div>", unsafe_allow_html=True)

            # ---- Language split + activity by weekday ----
            lang_col, weekday_col = st.columns(2)

            with lang_col:
                st.markdown('<div class="chart-section-title">Language split</div>', unsafe_allow_html=True)
                if not lang_df.empty:
                    fig_lang = px.pie(
                        lang_df,
                        names="language",
                        values="count",
                        hole=0.55,
                        color_discrete_sequence=["#1e3a8a", "#60a5fa", "#14b8a6"],
                    )
                    fig_lang.update_traces(textinfo="percent+label", textfont_size=11)
                    fig_lang.update_layout(
                        showlegend=False,
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=260,
                        font=dict(family="Inter, sans-serif", color="#374151"),
                    )
                    st.plotly_chart(fig_lang, use_container_width=True)

            with weekday_col:
                st.markdown('<div class="chart-section-title">Activity by day of week</div>', unsafe_allow_html=True)
                if weekday_df is not None:
                    fig_wd = px.bar(
                        weekday_df,
                        x="weekday",
                        y="count",
                        color_discrete_sequence=["#2563eb"],
                    )
                    fig_wd.update_layout(
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=260,
                        xaxis_title="",
                        yaxis_title="Videos",
                        font=dict(family="Inter, sans-serif", color="#374151"),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_wd, use_container_width=True)

            # ---- Activity over time ----
            if not activity_df.empty:
                st.markdown("<div style='height:1.8rem;'></div>", unsafe_allow_html=True)
                st.markdown('<div class="chart-section-title">Activity over time</div>', unsafe_allow_html=True)

                fig_area = px.area(
                    activity_df,
                    x="date",
                    y="count",
                    color_discrete_sequence=["#1e3a8a"],
                )
                fig_area.update_traces(line=dict(width=2), fillcolor="rgba(30,58,138,0.12)")
                fig_area.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=240,
                    xaxis_title="",
                    yaxis_title="Videos analyzed",
                    font=dict(family="Inter, sans-serif", color="#374151"),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_area, use_container_width=True)



    # ---- History ----
    elif nav == "History":

        st.subheader("🕘 Your analysis history")

        history = get_history(email)

        if not history:

            st.info(
                "You haven't analyzed any videos yet."
            )

        else:

            for item in history:

                with st.container(border=True):

                    st.markdown(
                        f"<div class='history-title'>📌 {item['title']}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        f"<div class='history-meta'>"
                        f"{item['timestamp']} · "
                        f"{item.get('language', 'english')} · "
                        f"<a href='{item['source']}' target='_blank'>"
                        f"{item['source']}</a>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        f"<div class='history-snippet'>"
                        f"{item['summary_snippet']}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )