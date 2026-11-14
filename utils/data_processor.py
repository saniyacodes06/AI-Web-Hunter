
import sqlite3
import pandas as pd
import json

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "signals.db"


def load_analyses():

    connection = sqlite3.connect(DB_PATH)

    df = pd.read_sql_query(
        "SELECT * FROM website_analyses",
        connection
    )

    connection.close()

    return df


def process_signals():

    df = load_analyses()

    if df.empty:
        print("No analysis records found.")
        return

    all_signals = []

    for _, row in df.iterrows():

        signals = json.loads(row["signals"])

        for signal in signals:
            signal["website"] = row["website_title"]
            signal["website_url"] = row["website_url"]
            signal["analyzed_at"] = row["analyzed_at"]

            all_signals.append(signal)

    signals_df = pd.DataFrame(all_signals)

    return df, signals_df


if __name__ == "__main__":

    result = process_signals()

    if result:
        website_df, signals_df = result

        print("\nWEBSITE ANALYSIS DATA")
        print(website_df[["website_title", "website_url"]])

        print("\nDETECTED SIGNALS")
        print(signals_df[["category", "score", "importance"]])

        print("\nSIGNAL SUMMARY")
        print(signals_df["category"].value_counts())
