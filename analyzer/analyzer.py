
from analyzer.ai_analyzer import analyze_with_ai
from utils.change_detector import detect_changes
from utils.database import initialize_database, save_analysis


def analyze_website(page_data):

    content = page_data["content"]
    website_title = page_data.get("title", "Unknown Website")
    website_url = page_data.get("url", "Unknown URL")

    # Step 1: Initialize database
    initialize_database()

    # Step 2: Detect website changes
    change_result = detect_changes(content, website_url)

    # Step 3: Detect business signals
    signal_categories = {
        "Hiring Signal": {
            "keywords": ["hiring", "careers", "job opening", "recruitment"],
            "score": 5
        },
        "Product Launch Signal": {
            "keywords": ["launch", "new product", "released"],
            "score": 8
        },
        "Funding Signal": {
            "keywords": ["funding", "investment", "raised"],
            "score": 10
        }
    }

    detected_signals = []
    content_lower = content.lower()

    for category, details in signal_categories.items():

        matched_keywords = [
            word for word in details["keywords"]
            if word in content_lower
        ]

        if matched_keywords:
            score = details["score"]

            importance = (
                "High" if score >= 8
                else "Medium" if score >= 5
                else "Low"
            )

            detected_signals.append({
                "category": category,
                "matched_keywords": matched_keywords,
                "score": score,
                "importance": importance
            })

    # Step 4: AI analysis
    ai_result = analyze_with_ai(content)

    # Step 5: Save results
    save_analysis(
        website_title,
        website_url,
        content,
        detected_signals,
        ai_result
    )

    # Step 6: Return structured results
    return {
        "website_title": website_title,
        "website_url": website_url,
        "change_result": change_result,
        "detected_signals": detected_signals,
        "ai_result": ai_result
    }
