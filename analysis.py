"""
Project Oasis: Creator Partnerships Trending TikTok Analysis

Loads a flattened trending-video CSV (one row per video) and produces a
creator-level summary table used for the one-screen view and the Q&A layer.

Usage:
    python analysis.py path/to/trending_tiktoks.csv [--out data/creator_summary.csv]

Expected input columns (rename via COLUMN_MAP below if yours differ):
    video_id, author, author_verified, views, likes, comments, shares
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Config: rename these if your CSV uses different column names
# ---------------------------------------------------------------------------
COLUMN_MAP = {
    "video_id": "video_id",
    "author": "author_name",
    "author_verified": "author_verified",
    "views": "views",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
}

MIN_VIDEOS_FOR_CONSISTENCY = 3  # videos needed for "high confidence"
TOP_VIEW_PERCENTILE_FOR_SCALE_PENALTY = 0.95  # top 5% by views treated as "already big"


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    missing = [c for c in COLUMN_MAP.values() if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV is missing expected columns: {missing}. "
            f"Update COLUMN_MAP at the top of analysis.py to match your data."
        )
    # Rename actual CSV column names to the internal standard names used below
    df = df.rename(columns={actual: internal for internal, actual in COLUMN_MAP.items()})
    # Drop rows with no views, since engagement rate is undefined without them
    df = df[df["views"] > 0].copy()
    return df


def compute_video_engagement(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["engagement_rate"] = (
        df["likes"].fillna(0) + df["comments"].fillna(0) + df["shares"].fillna(0)
    ) / df["views"]
    df["efficiency"] = df["engagement_rate"] / df["views"]
    return df


def build_creator_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Roll video-level rows up into one row per creator."""
    grouped = df.groupby("author")

    summary = grouped.agg(
        video_count=("video_id", "count"),
        median_engagement_rate=("engagement_rate", "median"),
        median_views=("views", "median"),
        max_views=("views", "max"),
        median_efficiency=("efficiency", "median"),
        author_verified=("author_verified", "max"),  # True if verified in any row
    ).reset_index()

    # Confidence flag: how much do we trust this creator's score?
    summary["confidence"] = summary["video_count"].apply(
        lambda n: "high" if n >= MIN_VIDEOS_FOR_CONSISTENCY else ("medium" if n >= 2 else "low")
    )

    # Scale flag: is this creator already operating at large reach?
    scale_cutoff = summary["median_views"].quantile(TOP_VIEW_PERCENTILE_FOR_SCALE_PENALTY)
    summary["already_large_reach"] = summary["median_views"] >= scale_cutoff

    return summary


def segment_creators(summary: pd.DataFrame) -> pd.DataFrame:
    """Assign each creator to Rising / Proven / Breakout."""
    engagement_cutoff = summary["median_engagement_rate"].median()

    def classify(row):
        strong_engagement = row["median_engagement_rate"] >= engagement_cutoff
        already_big = row["author_verified"] or row["already_large_reach"]
        one_off = row["video_count"] == 1 and row["max_views"] >= summary["max_views"].quantile(0.9)

        if one_off and not strong_engagement:
            return "Breakout"
        if strong_engagement and already_big:
            return "Proven"
        if strong_engagement and not already_big:
            return "Rising"
        return "Other"

    summary = summary.copy()
    summary["segment"] = summary.apply(classify, axis=1)
    return summary


def promising_score(summary: pd.DataFrame) -> pd.DataFrame:
    """Single sortable score: consistency-weighted engagement, penalized for already-large
    reach, and weighted down for low-confidence (single-video) creators so a lucky
    one-off post can't outrank a creator with a real, repeated pattern."""
    summary = summary.copy()
    scale_penalty = summary["already_large_reach"].map({True: 0.5, False: 1.0})
    verified_penalty = summary["author_verified"].map({True: 0.7, False: 1.0})
    confidence_weight = summary["confidence"].map({"high": 1.0, "medium": 0.8, "low": 0.4})
    summary["promising_score"] = (
        summary["median_engagement_rate"] * scale_penalty * verified_penalty * confidence_weight
    )
    return summary


def run(csv_path: str, out_path: str) -> pd.DataFrame:
    df = load_data(csv_path)
    df = compute_video_engagement(df)
    summary = build_creator_summary(df)
    summary = segment_creators(summary)
    summary = promising_score(summary)
    summary = summary.sort_values("promising_score", ascending=False).reset_index(drop=True)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_path, index=False)

    return summary


def print_headline(summary: pd.DataFrame):
    rising = summary[summary["segment"] == "Rising"].sort_values(
        "promising_score", ascending=False
    )
    undervalued = summary.sort_values("median_efficiency", ascending=False).iloc[0]

    print("\n=== Project Oasis: Headline Summary ===\n")
    print(f"Creators analyzed: {len(summary)}")
    print(f"Rising creators found: {len(rising)}")
    print("\nTop 5 Rising creators:")
    print(rising[["author", "median_engagement_rate", "video_count", "confidence"]].head(5).to_string(index=False))
    print(f"\nMost Undervalued: {undervalued['author']} "
          f"(engagement rate {undervalued['median_engagement_rate']:.2%}, "
          f"median views {int(undervalued['median_views'])})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project Oasis creator analysis")
    parser.add_argument("csv_path", help="Path to the trending TikTok CSV")
    parser.add_argument("--out", default="data/creator_summary.csv", help="Output path for creator summary CSV")
    args = parser.parse_args()

    try:
        summary = run(args.csv_path, args.out)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print_headline(summary)
    print(f"\nFull creator summary written to: {args.out}")
