
import os
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from scraper.crawler import discover_and_crawl

load_dotenv()

st.set_page_config(
    page_title="AI Web Signal Hunter",
    page_icon="🛰️",
    layout="wide"
)

# ---------- Styling ----------
st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
    max-width: 1450px;
}
.hero {
    padding: 28px;
    border-radius: 15px;
    background: linear-gradient(115deg, #101b32, #203b59);
    border: 1px solid #34516f;
    margin-bottom: 22px;
}
.hero h1 {
    color: #ffffff;
    margin: 0;
    font-size: 2rem;
}
.hero p {
    color: #c5d4e5;
    margin: 8px 0 0;
}
[data-testid="stMetric"] {
    background: #111827;
    padding: 16px;
    border: 1px solid #263244;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🛰️ AI Web Signal Hunter</h1>
    <p>Discover, crawl and explore public web information for market research.</p>
</div>
""", unsafe_allow_html=True)


# ---------- Helpers ----------
def get_page_text(page):
    for key in ["text", "content", "body", "cleaned_text"]:
        value = page.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def get_domain(page):
    domain = page.get("domain")
    if domain:
        return domain
    return urlparse(page.get("url", "")).netloc


# ---------- Session State ----------
defaults = {
    "pages": [],
    "research_topic": "",
    "crawl_date": "",
    "requested_pages": 25
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("### Research settings")

    topic = st.text_input(
        "Research topic",
        value="Problems small businesses face with WhatsApp automation"
    )

    keywords = st.text_input(
        "Optional keywords",
        value="pricing, setup, integration, support"
    )

    page_limit = st.slider(
        "Maximum pages to crawl",
        min_value=10,
        max_value=50,
        value=25,
        step=5
    )

    start = st.button(
        "🚀 Start research",
        type="primary",
        use_container_width=True
    )

    st.divider()
    st.markdown("**Research pipeline**")
    st.caption("Discover → Crawl → Clean → Deduplicate → Explore sources")


# ---------- Run Research ----------
if start:
    if not topic.strip():
        st.error("Please enter a research topic.")
        st.stop()

    progress = st.progress(0, text="Discovering relevant pages...")
    status = st.empty()

    def update_progress(current, total):
        percentage = min(current / max(total, 1), 1.0)
        progress.progress(
            percentage,
            text=f"Crawling pages... {current}/{total}"
        )

    try:
        pages = discover_and_crawl(
            topic,
            keywords,
            page_limit,
            progress_callback=update_progress
        )

        if not pages:
            st.error("No crawlable pages were found. Try another topic.")
            st.stop()

        st.session_state.pages = pages
        st.session_state.research_topic = topic
        st.session_state.crawl_date = datetime.now(
            timezone.utc
        ).isoformat()
        st.session_state.requested_pages = page_limit

        progress.progress(1.0, text="Research completed.")
        status.success(
            f"Successfully collected {len(pages)} unique pages."
        )

    except Exception as error:
        st.error(f"Research failed: {error}")
        st.stop()


# ---------- Dashboard ----------
pages = st.session_state.pages

if not pages:
    st.markdown("### Start your web research")
    st.write(
        "Enter a topic in the sidebar and start crawling publicly "
        "accessible web pages."
    )
    st.info(
        "This version focuses on real source discovery and content "
        "exploration. AI-generated market analysis is currently disabled."
    )
    st.stop()


domains = sorted({
    get_domain(page)
    for page in pages
    if get_domain(page)
})

total_words = sum(
    len(get_page_text(page).split())
    for page in pages
)

# ---------- Metrics ----------
st.markdown("### Research overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Pages crawled", len(pages))
c2.metric("Unique domains", len(domains))
c3.metric("Words collected", f"{total_words:,}")
c4.metric(
    "Target progress",
    f"{min(len(pages) / 25 * 100, 100):.0f}%"
)


st.caption(
    f"Research topic: {st.session_state.research_topic}"
)
st.caption(
    f"Research date: {st.session_state.crawl_date}"
)

st.divider()


# ---------- Domain Overview ----------
st.markdown("### Source distribution")

domain_counts = pd.Series(
    [get_domain(page) for page in pages]
).value_counts().reset_index()

domain_counts.columns = ["Domain", "Pages"]

left, right = st.columns([1.2, 1])

with left:
    st.markdown("**Pages collected per domain**")
    st.bar_chart(
        domain_counts.set_index("Domain"),
        height=300
    )

with right:
    st.markdown("**Research statistics**")
    st.write(f"- Total pages: {len(pages)}")
    st.write(f"- Unique domains: {len(domains)}")
    st.write(f"- Total words extracted: {total_words:,}")
    st.write(f"- Requested page limit: {st.session_state.requested_pages}")


st.divider()


# ---------- Source Explorer ----------
st.markdown("### Crawled source explorer")
st.write("Search, filter and inspect the content collected from each website.")

search_query = st.text_input(
    "Search sources",
    placeholder="Search by title, domain or page content..."
)

domain_options = ["All domains"] + domains

selected_domain = st.selectbox(
    "Filter by domain",
    domain_options
)

filtered_pages = []

for page in pages:
    title = page.get("title", "Untitled page")
    domain = get_domain(page)
    url = page.get("url", "")
    content = get_page_text(page)

    if selected_domain != "All domains" and domain != selected_domain:
        continue

    search_text = f"{title} {domain} {content}".lower()

    if search_query.lower() not in search_text:
        continue

    filtered_pages.append(page)


st.caption(f"Showing {len(filtered_pages)} of {len(pages)} sources.")

source_rows = []

for page in filtered_pages:
    source_rows.append({
        "Title": page.get("title", "Untitled page"),
        "Domain": get_domain(page),
        "Words": len(get_page_text(page).split()),
        "URL": page.get("url", ""),
        "Crawled": page.get("crawl_date", "—")
    })

source_df = pd.DataFrame(source_rows)

if not source_df.empty:
    st.dataframe(
        source_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn(
                "Source URL",
                display_text="Open source"
            ),
            "Title": st.column_config.TextColumn(
                "Page title",
                width="large"
            )
        }
    )

    selected_index = st.selectbox(
        "Inspect page content",
        range(len(filtered_pages)),
        format_func=lambda i: (
            f"{filtered_pages[i].get('title', 'Untitled page')}"
            f" — {get_domain(filtered_pages[i])}"
        )
    )

    selected_page = filtered_pages[selected_index]

    with st.expander("View extracted page content", expanded=True):
        st.markdown(
            f"**Title:** {selected_page.get('title', 'Untitled page')}"
        )
        st.markdown(
            f"**Domain:** {get_domain(selected_page)}"
        )

        source_url = selected_page.get("url", "")
        if source_url:
            st.markdown(f"[Open original webpage]({source_url})")

        content = get_page_text(selected_page)

        if content:
            st.text_area(
                "Extracted content",
                value=content,
                height=300,
                disabled=True
            )
        else:
            st.warning("No text content was stored for this page.")

else:
    st.info("No sources match your search.")


st.divider()


# ---------- Export ----------
st.markdown("### Export research data")

export_pages = []

for page in pages:
    export_pages.append({
        "title": page.get("title", ""),
        "domain": get_domain(page),
        "url": page.get("url", ""),
        "crawl_date": page.get("crawl_date", ""),
        "content": get_page_text(page)
    })

report = {
    "research_topic": st.session_state.research_topic,
    "crawl_date": st.session_state.crawl_date,
    "requested_pages": st.session_state.requested_pages,
    "pages_crawled": len(pages),
    "unique_domains": len(domains),
    "sources": export_pages
}

col1, col2 = st.columns(2)

with col1:
    st.download_button(
        "⬇️ Download sources CSV",
        data=pd.DataFrame(export_pages).to_csv(
            index=False
        ).encode("utf-8"),
        file_name="web_research_sources.csv",
        mime="text/csv",
        use_container_width=True
    )

with col2:
    st.download_button(
        "⬇️ Download research JSON",
        data=json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ).encode("utf-8"),
        file_name="web_research_report.json",
        mime="application/json",
        use_container_width=True
    )


st.caption(
    "AI analysis is disabled in this version. "
    "All displayed source information comes from the actual crawl."
)
