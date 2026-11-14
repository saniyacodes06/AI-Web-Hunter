
import os
import hashlib


def detect_changes(current_content, website_url):

    website_id = hashlib.md5(
        website_url.encode()
    ).hexdigest()

    folder = "data/baselines"
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(
        folder, f"{website_id}.txt"
    )

    if not os.path.exists(file_path):

        with open(file_path, "w") as file:
            file.write(current_content)

        return {
            "status": "First Crawl",
            "changed": False
        }

    with open(file_path, "r") as file:
        previous_content = file.read()

    if current_content != previous_content:

        with open(file_path, "w") as file:
            file.write(current_content)

        return {
            "status": "Changes Detected",
            "changed": True
        }

    return {
        "status": "No Changes",
        "changed": False
    }
