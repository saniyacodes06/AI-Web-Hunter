import os, json, re
from datetime import datetime, timezone
from urllib.parse import urlparse
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from scraper.crawler import discover_and_crawl
from analyzer.ai_analyzer import analyze_pages
from analyzer.opportunities import build_opportunities

load_dotenv()
print("MODEL LOADED:", os.getenv("GROQ_MODEL"))
st.set_page_config(page_title="AI Web Signal Hunter", page_icon="🛰️", layout="wide")

st.markdown("""
<style>
  .block-container {padding-top: 1.8rem; max-width: 1450px;}
  [data-testid="stMetric"] {background: #111827; padding: 16px 18px; border: 1px solid #263244; border-radius: 12px;}
  .hero {padding: 26px 28px; border-radius: 16px; background: linear-gradient(115deg,#101b32,#172b46); border: 1px solid #29415f; margin-bottom: 20px;}
  .hero h1 {margin:0; color:#f8fafc; font-size:2rem;}
  .hero p {margin:8px 0 0; color:#b8c7dc;}
  .small-muted {color:#94a3b8; font-size:0.88rem;}
  div[data-testid="stExpander"] {border:1px solid #293548; border-radius:10px;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🛰️ AI Web Signal Hunter</h1>
  <p>Turn public web conversations into evidence-backed market signals and opportunities.</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Research settings")
    topic = st.text_input("Research topic", "Problems small businesses face with WhatsApp automation")
    keywords = st.text_input("Optional keywords", "pricing, setup, integration, support")
    page_limit = st.slider("Maximum pages to crawl", 10, 50, 25, 5)
    provider = st.selectbox("AI provider", ["Groq", "Gemini"])
    st.caption("The provider key is read from your local .env file.")
    run = st.button("🚀 Start research", type="primary", use_container_width=True)
    st.divider()
    st.markdown("**Pipeline**")
    st.caption("Discover → Crawl → Clean & deduplicate → AI signals → Rank opportunities")

if "pages" not in st.session_state:
    st.session_state.pages = []
    st.session_state.signals = []
    st.session_state.opportunities = []
    st.session_state.run_meta = {}

if run:
    if not topic.strip():
        st.error("Enter a research topic first.")
        st.stop()
    key_name = "GROQ_API_KEY" if provider == "Groq" else "GEMINI_API_KEY"
    if not os.getenv(key_name):
        st.error(f"Missing {key_name}. Add it to your .env file, then restart Streamlit.")
        st.stop()

    progress = st.progress(0, text="Discovering relevant public pages…")
    status = st.empty()
    try:
        pages = discover_and_crawl(topic, keywords, page_limit, progress_callback=lambda n, total: (
            progress.progress(min(0.55, 0.05 + 0.5*n/max(total,1)),
                              text=f"Crawling public pages… {n}/{total}")
        ))
        st.session_state.pages = pages
        if not pages:
            st.error("No crawlable pages were found. Try a broader topic or different keywords.")
            st.stop()

        domains = sorted({p["domain"] for p in pages})
        progress.progress(0.60, text=f"Cleaned {len(pages)} unique pages. Analyzing with {provider}…")
        signals = analyze_pages(pages, provider)
        progress.progress(0.90, text="Grouping recurring signals and ranking opportunities…")
        opportunities = build_opportunities(signals)
        st.session_state.signals = signals
        st.session_state.opportunities = opportunities
        st.session_state.run_meta = {
            "topic": topic, "provider": provider,
            "crawl_date": datetime.now(timezone.utc).isoformat(),
            "domains": domains, "requested": page_limit
        }
        progress.progress(1.0, text="Research complete.")
        status.success(f"Completed: {len(pages)} unique pages across {len(domains)} domains; {len(signals)} signals analyzed.")
        if len(pages) < 25 or len(domains) < 3:
            st.warning(f"Assignment target is 25 pages across 3+ domains. This run reached {len(pages)} pages across {len(domains)} domains. Do not claim the target was met unless the crawl actually reaches it.")
    except Exception as e:
        st.error(f"Research stopped: {e}")
        st.info("Check your API key, network connection, and provider rate limits. Your source code does not fabricate missing pages or evidence.")

pages = st.session_state.pages
signals = st.session_state.signals
opps = st.session_state.opportunities
meta = st.session_state.run_meta

if not signals:
    st.markdown("### Start with a research question")
    st.write("Example: *What features are people requesting from AI meeting assistants?*")
    st.info("Run a crawl to populate the dashboard. Results are based on pages the crawler can actually access; inaccessible or disallowed pages are skipped.")
    st.stop()

domains = meta.get("domains", [])
useful = [s for s in signals if s.get("category") != "Irrelevant"]
c1,c2,c3,c4 = st.columns(4)
c1.metric("Pages crawled", len(pages))
c2.metric("Useful signals", len(useful))
c3.metric("Domains", len(domains))
c4.metric("Opportunities", len(opps))

st.markdown("### Research overview")
left, right = st.columns([1.05, 1])
with left:
    st.markdown("**Signal categories**")
    cat_counts = pd.Series([s["category"] for s in signals]).value_counts().rename_axis("Category").reset_index(name="Count")
    st.plotly_chart(px.pie(cat_counts, names="Category", values="Count", hole=.55,
                           color_discrete_sequence=px.colors.qualitative.Safe), use_container_width=True)
with right:
    st.markdown("**Top recurring themes**")
    if opps:
        theme_df = pd.DataFrame([{"Theme": o["theme"], "Rank score": o["rank_score"], "Sources": o["source_count"]} for o in opps[:8]])
        st.plotly_chart(px.bar(theme_df, x="Rank score", y="Theme", orientation="h",
                               hover_data=["Sources"], color="Rank score",
                               color_continuous_scale="Blues"), use_container_width=True)
    else:
        st.caption("No recurring themes could be grouped from the current signals.")

st.markdown("### Top opportunity briefs")
if opps:
    for i, o in enumerate(opps[:5], 1):
        with st.expander(f"#{i} · {o['theme']}  —  score {o['rank_score']}/100", expanded=(i == 1)):
            st.write(o["what"])
            st.markdown(f"**Why now:** {o['why_now']}")
            st.markdown(f"**Possible angle:** {o['angle']}")
            st.markdown(f"**Next validation step:** {o['next_step']}")
            st.caption(f"Based on {o['source_count']} source(s). Ranking is a prioritization aid, not an objective market fact.")
            for url in o["sources"][:5]:
                st.markdown(f"- [{url}]({url})")

st.markdown("### Findings explorer")
categories = ["All"] + sorted({s["category"] for s in signals})
f1, f2 = st.columns([1, 2])
selected_cat = f1.selectbox("Filter by category", categories)
min_score = f2.slider("Minimum relevance score", 0, 100, 0)
filtered = [s for s in signals if (selected_cat == "All" or s["category"] == selected_cat)
            and s["relevance_score"] >= min_score]
table_rows = [{
    "Category": s["category"], "Summary": s["summary"],
    "Relevance": s["relevance_score"], "Urgency": s["urgency_score"],
    "Confidence": s["confidence_score"], "Domain": s["domain"], "Source": s["source_url"]
} for s in filtered]
df = pd.DataFrame(table_rows)
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={"Source": st.column_config.LinkColumn("Source", display_text="Open source"),
                   "Summary": st.column_config.TextColumn("Summary", width="large")}
)
if filtered:
    selected = st.selectbox("Inspect a finding", range(len(filtered)),
                            format_func=lambda i: f"{filtered[i]['category']} · {filtered[i]['summary'][:90]}")
    s = filtered[selected]
    with st.container(border=True):
        st.markdown(f"**{s['category']}**")
        st.write(s["summary"])
        st.markdown(f"> “{s['evidence']}”")
        st.caption(f"Source: {s['source_url']}")
        st.markdown(f"**Why these scores:** {s['score_reason']}")
        a,b,c = st.columns(3)
        a.metric("Relevance", f"{s['relevance_score']}/100")
        b.metric("Urgency", f"{s['urgency_score']}/100")
        c.metric("Confidence", f"{s['confidence_score']}/100")

st.markdown("### Crawled sources")
source_df = pd.DataFrame([{"Title":p["title"], "Domain":p["domain"], "Crawled":p["crawl_date"], "URL":p["url"]} for p in pages])
st.dataframe(source_df, use_container_width=True, hide_index=True,
             column_config={"URL": st.column_config.LinkColumn("URL")})

st.markdown("### Export")
col_a, col_b = st.columns(2)
payload = {"research": meta, "pages": pages, "signals": signals, "opportunities": opps}
with col_a:
    st.download_button("⬇️ Download findings CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="signal_findings.csv", mime="text/csv", use_container_width=True)
with col_b:
    st.download_button("⬇️ Download full report JSON", json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
                       file_name="signal_hunter_report.json", mime="application/json", use_container_width=True)

st.caption("Ranking formula: 35% average relevance + 25% average urgency + 20% average confidence + 20% source frequency (capped at 5 sources).")
st.caption(f"Provider: {meta.get('provider','—')} · Crawl date: {meta.get('crawl_date','—')}")
