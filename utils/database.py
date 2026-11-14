"""SQLite storage for topics, pages, signals, opportunities and legacy analyses."""

import json
import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS website_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    website_title TEXT,
    website_url TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content TEXT,
    signals TEXT,
    ai_analysis TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    keywords TEXT,
    page_limit INTEGER,
    permitted_domains TEXT,
    provider TEXT,
    status TEXT DEFAULT 'running',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    pages_found INTEGER DEFAULT 0,
    pages_crawled INTEGER DEFAULT 0,
    pages_kept INTEGER DEFAULT 0,
    signals_count INTEGER DEFAULT 0,
    opportunities_count INTEGER DEFAULT 0,
    warnings TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    domain TEXT,
    title TEXT,
    published_at TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content TEXT,
    word_count INTEGER,
    content_hash TEXT,
    relevance_score REAL,
    status TEXT,
    error TEXT,
    search_query TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    page_id INTEGER,
    signal_type TEXT,
    category TEXT,
    entity TEXT,
    summary TEXT,
    evidence TEXT,
    why_it_matters TEXT,
    evidence_score REAL,
    confidence REAL,
    relevance REAL,
    recency REAL,
    evidence_verified INTEGER,
    extraction_method TEXT,
    source_url TEXT,
    source_domain TEXT,
    source_title TEXT,
    published_at TEXT,
    topic TEXT,
    keywords TEXT,
    dedupe_key TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(id),
    FOREIGN KEY (page_id) REFERENCES pages(id)
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    rank_no INTEGER,
    theme TEXT,
    theme_label TEXT,
    title TEXT,
    summary TEXT,
    why_now TEXT,
    target_customer TEXT,
    recommended_action TEXT,
    risks TEXT,
    signal_count INTEGER,
    source_count INTEGER,
    avg_evidence_score REAL,
    avg_confidence REAL,
    recency_score REAL,
    diversity_score REAL,
    score REAL,
    score_breakdown TEXT,
    evidence TEXT,
    entities TEXT,
    signal_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_pages_run ON pages(run_id);
CREATE INDEX IF NOT EXISTS idx_signals_run ON signals(run_id);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_opportunities_run ON opportunities(run_id);
"""


def _connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(verbose=False):
    connection = _connect()
    try:
        connection.executescript(SCHEMA)
        connection.commit()
    finally:
        connection.close()
    if verbose:
        print(f"Database initialized at {DB_PATH}")


def _json_dumps(value):
    return json.dumps(value or [], ensure_ascii=False)


def _json_loads(value, default):
    if value is None or value == "":
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def create_run(
    topic,
    keywords=None,
    page_limit=30,
    permitted_domains=None,
    provider="groq",
):
    initialize_database()
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO runs
            (topic, keywords, page_limit, permitted_domains, provider, status)
            VALUES (?, ?, ?, ?, ?, 'running')
            """,
            (
                topic,
                _json_dumps(keywords),
                int(page_limit),
                _json_dumps(permitted_domains),
                provider,
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def finish_run(
    run_id,
    status="completed",
    pages_found=0,
    pages_crawled=0,
    pages_kept=0,
    signals_count=0,
    opportunities_count=0,
    warnings=None,
    error=None,
):
    connection = _connect()
    try:
        connection.execute(
            """
            UPDATE runs
            SET status = ?, finished_at = CURRENT_TIMESTAMP,
                pages_found = ?, pages_crawled = ?, pages_kept = ?,
                signals_count = ?, opportunities_count = ?,
                warnings = ?, error = ?
            WHERE id = ?
            """,
            (
                status,
                int(pages_found),
                int(pages_crawled),
                int(pages_kept),
                int(signals_count),
                int(opportunities_count),
                _json_dumps(warnings),
                error,
                run_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def save_page(run_id, page, search_query=None, status="success", error=None):
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO pages
            (run_id, url, domain, title, published_at, content, word_count,
             content_hash, relevance_score, status, error, search_query)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                page.get("url"),
                page.get("domain"),
                page.get("title"),
                page.get("published_at"),
                page.get("content"),
                int(page.get("word_count") or 0),
                page.get("content_hash"),
                float(page.get("relevance_score") or 0),
                status,
                error,
                search_query,
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def save_signal(run_id, page_id, signal):
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO signals
            (run_id, page_id, signal_type, category, entity, summary, evidence,
             why_it_matters, evidence_score, confidence, relevance, recency,
             evidence_verified, extraction_method, source_url, source_domain,
             source_title, published_at, topic, keywords, dedupe_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                page_id,
                signal.get("signal_type"),
                signal.get("category"),
                signal.get("entity"),
                signal.get("summary"),
                signal.get("evidence"),
                signal.get("why_it_matters"),
                float(signal.get("evidence_score") or 0),
                float(signal.get("confidence") or 0),
                float(signal.get("relevance") or 0),
                float(signal.get("recency") or 0),
                1 if signal.get("evidence_verified") else 0,
                signal.get("extraction_method"),
                signal.get("source_url"),
                signal.get("source_domain"),
                signal.get("source_title"),
                signal.get("published_at"),
                signal.get("topic"),
                _json_dumps(signal.get("keywords")),
                signal.get("dedupe_key"),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def save_opportunity(run_id, rank_no, opportunity):
    connection = _connect()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO opportunities
            (run_id, rank_no, theme, theme_label, title, summary, why_now,
             target_customer, recommended_action, risks, signal_count,
             source_count, avg_evidence_score, avg_confidence, recency_score,
             diversity_score, score, score_breakdown, evidence, entities,
             signal_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                int(rank_no),
                opportunity.get("theme"),
                opportunity.get("theme_label"),
                opportunity.get("title"),
                opportunity.get("summary"),
                opportunity.get("why_now"),
                opportunity.get("target_customer"),
                opportunity.get("recommended_action"),
                opportunity.get("risks"),
                int(opportunity.get("signal_count") or 0),
                int(opportunity.get("source_count") or 0),
                float(opportunity.get("avg_evidence_score") or 0),
                float(opportunity.get("avg_confidence") or 0),
                float(opportunity.get("recency_score") or 0),
                float(opportunity.get("diversity_score") or 0),
                float(opportunity.get("score") or 0),
                json.dumps(opportunity.get("score_breakdown") or {}, ensure_ascii=False),
                json.dumps(opportunity.get("evidence") or [], ensure_ascii=False),
                _json_dumps(opportunity.get("entities")),
                _json_dumps(opportunity.get("signal_ids")),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def save_opportunities(run_id, opportunities):
    return [
        save_opportunity(run_id, rank, opportunity)
        for rank, opportunity in enumerate(opportunities, start=1)
    ]


def _run_to_dict(row):
    if row is None:
        return None
    data = dict(row)
    data["keywords"] = _json_loads(data.get("keywords"), [])
    data["permitted_domains"] = _json_loads(data.get("permitted_domains"), [])
    data["warnings"] = _json_loads(data.get("warnings"), [])
    return data


def get_run(run_id):
    connection = _connect()
    try:
        row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _run_to_dict(row)
    finally:
        connection.close()


def get_latest_run():
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return _run_to_dict(row)
    finally:
        connection.close()


def get_runs(limit=25):
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (int(limit),)
        ).fetchall()
        return [_run_to_dict(row) for row in rows]
    finally:
        connection.close()


def get_runs_dataframe(limit=25):
    return pd.DataFrame(get_runs(limit=limit))


def get_pages_dataframe(run_id):
    connection = _connect()
    try:
        return pd.read_sql_query(
            """
            SELECT id, url, domain, title, published_at, fetched_at,
                   word_count, relevance_score, status, search_query
            FROM pages
            WHERE run_id = ?
            ORDER BY id
            """,
            connection,
            params=(run_id,),
        )
    finally:
        connection.close()


def get_signals_dataframe(run_id):
    connection = _connect()
    try:
        return pd.read_sql_query(
            """
            SELECT id, signal_type, category, entity, summary, evidence,
                   why_it_matters, evidence_score, confidence, relevance,
                   recency, evidence_verified, extraction_method, source_url,
                   source_domain, source_title, published_at
            FROM signals
            WHERE run_id = ?
            ORDER BY evidence_score DESC, confidence DESC, id
            """,
            connection,
            params=(run_id,),
        )
    finally:
        connection.close()


def get_opportunities_dataframe(run_id, parse_json=False):
    connection = _connect()
    try:
        frame = pd.read_sql_query(
            """
            SELECT id, rank_no, theme, theme_label, title, summary, why_now,
                   target_customer, recommended_action, risks, signal_count,
                   source_count, avg_evidence_score, avg_confidence,
                   recency_score, diversity_score, score, score_breakdown,
                   evidence, entities, signal_ids
            FROM opportunities
            WHERE run_id = ?
            ORDER BY rank_no
            """,
            connection,
            params=(run_id,),
        )
    finally:
        connection.close()

    if parse_json and not frame.empty:
        for column, default in (
            ("score_breakdown", {}),
            ("evidence", []),
            ("entities", []),
            ("signal_ids", []),
        ):
            frame[column] = frame[column].apply(
                lambda value: _json_loads(value, default)
            )
    return frame


def get_run_frames(run_id):
    return {
        "run": get_run(run_id),
        "pages": get_pages_dataframe(run_id),
        "signals": get_signals_dataframe(run_id),
        "opportunities": get_opportunities_dataframe(run_id, parse_json=True),
    }


# ---------------------------------------------------------------------------
# Legacy website-monitoring functions kept for backward compatibility.
# ---------------------------------------------------------------------------


def save_analysis(website_title, website_url, content, signals, ai_analysis):
    initialize_database()
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO website_analyses
            (website_title, website_url, content, signals, ai_analysis)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                website_title,
                website_url,
                content,
                json.dumps(signals, ensure_ascii=False),
                ai_analysis,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def get_analysis_history():
    initialize_database()
    connection = _connect()
    try:
        return pd.read_sql_query(
            """
            SELECT id, website_title, website_url, analyzed_at,
                   signals, ai_analysis
            FROM website_analyses
            ORDER BY analyzed_at DESC
            """,
            connection,
        )
    finally:
        connection.close()
