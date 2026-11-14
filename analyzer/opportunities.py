
import re

def build_opportunities(signals):
    groups = []

    useful = [
        s for s in signals
        if s.get("category") != "Irrelevant"
        and s.get("relevance_score", 0) >= 25
    ]

    def tokens(text):
        return set(re.findall(r"[a-z]{4,}", text.lower()))

    for signal in useful:
        words = tokens(signal["summary"])
        matched = None

        for group in groups:
            if group["category"] != signal["category"]:
                continue

            common = len(words & group["tokens"])
            total = len(words | group["tokens"])

            if total and common / total >= 0.18:
                matched = group
                break

        if matched:
            matched["items"].append(signal)
            matched["tokens"].update(words)
        else:
            groups.append({
                "category": signal["category"],
                "tokens": words,
                "items": [signal]
            })

    opportunities = []

    for group in groups:
        items = group["items"]

        relevance = sum(x["relevance_score"] for x in items) / len(items)
        urgency = sum(x["urgency_score"] for x in items) / len(items)
        confidence = sum(x["confidence_score"] for x in items) / len(items)

        domains = set(x["domain"] for x in items)
        frequency = min(len(domains), 5) / 5 * 100

        score = round(
            0.35 * relevance
            + 0.25 * urgency
            + 0.20 * confidence
            + 0.20 * frequency
        )

        best = max(
            items,
            key=lambda x: x["relevance_score"] + x["urgency_score"]
        )

        opportunities.append({
            "theme": best["summary"][:100],
            "category": group["category"],
            "rank_score": score,
            "source_count": len(domains),
            "what": best["summary"],
            "why_now": "This theme appears in multiple research signals and deserves further validation.",
            "angle": "Explore a product or service addressing this recurring problem.",
            "next_step": "Interview five potential customers to validate the problem.",
            "sources": list(set(x["source_url"] for x in items)),
            "evidence": [x["evidence"] for x in items if x.get("evidence")]
        })

    return sorted(
        opportunities,
        key=lambda x: x["rank_score"],
        reverse=True
    )
