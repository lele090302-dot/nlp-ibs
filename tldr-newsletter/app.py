"""
app.py - Streamlit frontend for newsletter signup and admin review.
Run with: streamlit run app.py
"""

import os
import streamlit as st
from db import (
    init_db, add_user, unsubscribe, log_feedback,
    get_review_queue, get_latest_run_id, update_article_status,
)
from pipeline import run_pipeline, run_pipeline_force, stage_pipeline, send_pipeline

init_db()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TL;DR Newsletter",
    page_icon="⚡",
    layout="centered",
)

st.markdown("""
<style>
    .main { max-width: 720px; }
    h1 { font-size: 2.2rem !important; }
    .stCheckbox label { font-size: 15px; }
</style>
""", unsafe_allow_html=True)

# ── Query param handlers ──────────────────────────────────────────────────────
params = st.query_params

# Subscriber feedback (thumbs up/down from email links)
if params.get("feedback") == "1":
    email      = params.get("email", "")
    article_url = params.get("url", "")
    article_source = params.get("source", "")
    article_topic  = params.get("topic", "")
    signal_raw = params.get("signal", "0")
    try:
        signal = int(signal_raw)
        if email and article_url and signal in (1, -1):
            log_feedback(email, article_url, article_source, article_topic, signal)
            emoji = "👍" if signal == 1 else "👎"
            st.success(f"{emoji} Feedback recorded - future newsletters will reflect your preferences.")
        else:
            st.warning("Invalid feedback link.")
    except ValueError:
        st.warning("Invalid feedback signal.")
    st.stop()

# Admin approve/reject from email links
if params.get("admin_action") in ("approve", "reject"):
    action  = params.get("admin_action")
    run_id  = params.get("run_id", "")
    url     = params.get("url", "")
    if run_id and url:
        update_article_status(run_id, url, action)
        emoji = "✅" if action == "approve" else "❌"
        st.success(f"{emoji} Article **{action}d**. You can close this tab.")
    else:
        st.warning("Invalid admin action link.")
    st.stop()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚡ TL;DR Newsletter")
st.markdown(
    "AI-curated digest of the top 8-10 stories in your chosen topics, "
    "delivered to your inbox."
)
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_subscribe, tab_unsubscribe, tab_demo, tab_admin = st.tabs([
    "Subscribe", "Unsubscribe", "🔬 Live Demo", "🛠 Admin"
])

# ── Subscribe Tab ─────────────────────────────────────────────────────────────
with tab_subscribe:
    st.subheader("Customize your newsletter")

    with st.form("signup_form"):
        name  = st.text_input("Your name", placeholder="Jane Doe")
        email = st.text_input("Email address", placeholder="jane@example.com")

        st.markdown("**Choose your topics** (pick 1-5)")
        col1, col2 = st.columns(2)
        with col1:
            t_genai   = st.checkbox("🤖 AI")
            t_fintech = st.checkbox("💳 Fintech")
            t_tech    = st.checkbox("💻 Tech")
        with col2:
            t_startups = st.checkbox("🚀 Startups")
            t_crypto   = st.checkbox("₿ Crypto")

        st.markdown("**Delivery frequency**")
        frequency = st.radio(
            "Delivery frequency", ["Daily", "Weekly"],
            horizontal=True, label_visibility="collapsed"
        )

        submitted = st.form_submit_button("Subscribe →", use_container_width=True)

    if submitted:
        selected_topics = []
        if t_genai:    selected_topics.append("AI")
        if t_fintech:  selected_topics.append("Fintech")
        if t_tech:     selected_topics.append("Tech")
        if t_startups: selected_topics.append("Startups")
        if t_crypto:   selected_topics.append("Crypto")

        if not name.strip():
            st.error("Please enter your name.")
        elif "@" not in email or "." not in email:
            st.error("Please enter a valid email address.")
        elif not selected_topics:
            st.error("Please select at least one topic.")
        else:
            success, message = add_user(name.strip(), email.strip(), selected_topics, frequency.lower())
            if success:
                st.success(f"✅ {message} You'll receive your first newsletter soon.")
            else:
                st.error(message)

# ── Unsubscribe Tab ───────────────────────────────────────────────────────────
with tab_unsubscribe:
    st.subheader("Unsubscribe")
    unsub_email = st.text_input("Enter your email to unsubscribe", key="unsub")
    if st.button("Unsubscribe", use_container_width=True):
        if "@" not in unsub_email:
            st.error("Please enter a valid email.")
        else:
            unsubscribe(unsub_email.strip())
            st.success("You've been unsubscribed.")

# ── Live Demo Tab ─────────────────────────────────────────────────────────────
with tab_demo:
    st.subheader("Run the full pipeline")
    st.markdown(
        "Fetches articles, ranks them, builds newsletters, and sends via Amazon SES. "
        "Requires `.env` to be configured with active subscribers in the DB."
    )

    if st.button("🚀 Run pipeline now", use_container_width=True):
        with st.spinner("Running pipeline... this may take 30-60 seconds."):
            try:
                run_pipeline_force()
                st.success("✅ Pipeline completed! Check your inbox.")
            except Exception as e:
                st.error(f"Pipeline error: {e}")

    st.divider()
    st.markdown("**Send a sample newsletter** to a specific email:")

    preview_email = st.text_input("Send preview to email", placeholder="you@example.com")
    preview_name  = st.text_input("Your name", placeholder="Jane", value="Demo User")

    if st.button("📧 Send sample email", use_container_width=True):
        if "@" not in preview_email:
            st.error("Please enter a valid email address.")
        else:
            from newsletter_builder import build_html
            from sender import send_newsletter
            sample_articles = [
                {
                    "title": "OpenAI releases GPT-5 with reasoning improvements",
                    "source": "TechCrunch", "topic": "AI",
                    "url": "https://techcrunch.com",
                    "summary": "OpenAI has launched GPT-5, featuring improved reasoning and a new thinking mode. It outperforms its predecessor on all major benchmarks and is available via API today.",
                    "reading_time": 3,
                },
                {
                    "title": "Stripe raises $1B at $65B valuation",
                    "source": "Bloomberg", "topic": "Fintech",
                    "url": "https://bloomberg.com",
                    "summary": "Stripe closed a $1B funding round at a $65B valuation to expand into new markets and accelerate AI-powered financial tools.",
                    "reading_time": 2,
                },
            ]
            html = build_html(preview_name, preview_email, ["AI", "Fintech"], sample_articles)
            with st.spinner("Sending via Amazon SES..."):
                success = send_newsletter(preview_email, "TL;DR Newsletter - Sample Issue", html)
            if success:
                st.success(f"✅ Sample email sent to {preview_email}!")
            else:
                st.error("Failed to send. Check your AWS credentials in `.env`.")

    st.divider()
    st.markdown("**Preview newsletter HTML** in browser (no email sent):")
    if st.button("Generate preview", use_container_width=True):
        from newsletter_builder import build_html
        sample_articles = [
            {
                "title": "OpenAI releases GPT-5 with reasoning improvements",
                "source": "TechCrunch", "topic": "AI",
                "url": "https://techcrunch.com",
                "summary": "OpenAI has launched GPT-5 with improved reasoning and a new thinking mode.",
                "reading_time": 3,
            },
        ]
        html = build_html("Demo User", "demo@example.com", ["AI"], sample_articles)
        st.components.v1.html(html, height=700, scrolling=True)

# ── Admin Tab ─────────────────────────────────────────────────────────────────
with tab_admin:
    st.subheader("🛠 Admin Review Queue")
    st.markdown(
        "Review AI-ranked article candidates before they go out. "
        "Approve any stories to include them - approved picks go first, "
        "AI fills remaining slots to always deliver **8-10 stories**. "
        "If you approve nothing, the AI's top 10 are sent automatically."
    )

    # Admin actions
    col_stage, col_send = st.columns(2)
    with col_stage:
        if st.button("📥 Stage new batch", use_container_width=True,
                     help="Fetch articles, rank top 15, save to queue, email admin"):
            with st.spinner("Fetching and ranking articles..."):
                try:
                    run_id = stage_pipeline()
                    st.success(f"✅ Staged! run_id: `{run_id}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Stage error: {e}")

    with col_send:
        if st.button("📤 Send approved now", use_container_width=True,
                     help="Send newsletters using approved articles (or AI fallback)"):
            with st.spinner("Sending newsletters..."):
                try:
                    run_id = get_latest_run_id()
                    send_pipeline(run_id=run_id)
                    st.success("✅ Newsletters sent!")
                except Exception as e:
                    st.error(f"Send error: {e}")

    st.divider()

    # Load latest queue
    run_id = get_latest_run_id()
    if not run_id:
        st.info("No review queue yet. Click 'Stage new batch' to fetch articles.")
    else:
        articles = get_review_queue(run_id=run_id)
        pending  = [a for a in articles if a["status"] == "pending"]
        approved = [a for a in articles if a["status"] == "approved"]
        rejected = [a for a in articles if a["status"] == "rejected"]

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", len(articles))
        m2.metric("Pending", len(pending))
        m3.metric("Approved", len(approved), delta=f"{len(approved)}/10 needed")
        m4.metric("Rejected", len(rejected))

        st.caption(f"Run ID: `{run_id}`")
        st.divider()

        # Article cards
        for a in articles:
            status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(a["status"], "?")
            score_pct = int((a.get("relevance_score") or 0) * 100)

            with st.container():
                col_info, col_actions = st.columns([4, 1])

                with col_info:
                    st.markdown(
                        f"{status_emoji} **[{a['title']}]({a['url']})**  \n"
                        f"<span style='font-size:12px;color:#888;'>"
                        f"{a.get('source','?')} &middot; {a.get('topic','?')} &middot; "
                        f"{a.get('reading_time',1)} min &middot; Score: {score_pct}%"
                        f"</span>",
                        unsafe_allow_html=True,
                    )
                    if a.get("summary"):
                        st.caption(a["summary"])

                with col_actions:
                    if a["status"] != "approved":
                        if st.button("✅", key=f"approve_{a['id']}",
                                     help="Approve this article"):
                            update_article_status(run_id, a["url"], "approved")
                            st.rerun()
                    if a["status"] != "rejected":
                        if st.button("❌", key=f"reject_{a['id']}",
                                     help="Reject this article"):
                            update_article_status(run_id, a["url"], "rejected")
                            st.rerun()

                st.divider()

