from collections import defaultdict
import re

def _tokens(text):
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in {
        "about","their","there","which","would","could","should","these","those","with","from","have","they","this"
    }}

def build_opportunities(signals):
    groups = []
    useful = [s for s in signals if s.get("category") != "Irrelevant" and s.get("relevance_score",0) >= 25]
    # Greedy similarity grouping based on category and shared summary terms.
    for signal in useful:
        words = _tokens(signal["summary"])
        best, best_score = None, 0
        for group in groups:
            if group["category"] != signal["category"]:
                continue
            base = group["tokens"]
            score = len(words & base) / max(1, len(words | base))
            if score > best_score:
                best, best_score = group, score
        if best is not None and best_score >= 0.18:
            best["items"].append(signal)
            best["tokens"] |= words
        else:
            groups.append({"category":signal["category"],"tokens":words,"items":[signal]})

    opportunities = []
    for group in groups:
        items = group["items"]
        avg_rel = sum(x["relevance_score"] for x in items)/len(items)
        avg_urg = sum(x["urgency_score"] for x in items)/len(items)
        avg_conf = sum(x["confidence_score"] for x in items)/len(items)
        domains = {x["domain"] for x in items}
        # Transparent formula: 35% relevance + 25% urgency + 20% confidence + 20% frequency (capped at 5).
        frequency = min(len(domains),5)/5*100
        score = round(.35*avg_rel + .25*avg_urg + .20*avg_conf + .20*frequency)
        best = max(items, key=lambda x: x["relevance_score"] + x["urgency_score"])
        sources = list(dict.fromkeys(x["source_url"] for x in items))
        theme = best["summary"].rstrip(".")
        opportunities.append({
            "theme":theme[:100], "category":group["category"], "rank_score":score,
            "source_count":len(domains),
            "what":f"{len(items)} related signal(s) appeared across {len(domains)} distinct domain(s). {best['summary']}",
            "why_now":"The theme recurs across independently crawled public sources. Validate whether the need is current and commercially important before investing.",
            "angle":f"Explore a focused solution or feature addressing this {group['category'].lower()} for the audience described in the evidence.",
            "next_step":"Interview 5 people from the affected audience and test whether they experience this problem frequently enough to pay for a solution.",
            "sources":sources, "evidence":[x["evidence"] for x in items if x.get("evidence")]
        })
    return sorted(opportunities, key=lambda x:(x["rank_score"],x["source_count"]), reverse=True)
