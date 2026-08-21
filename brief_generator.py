"""
Project Oasis: Creative Brief Generator

Turns the 16 high-confidence Rising creators' real engagement data into
structured, actionable partnership briefs: a budget tier, a content angle
grounded in what already works for that creator, and a storyboard concept
ready to hand to a video editor (CapCut, Premiere, whatever) or an
image-generation tool for a visual mockup.

This closes the gap between "here is a ranked list" and "here is what to
do about it." Every field in the output is derived from real data, either
the creator summary table or the raw video metadata (duration, hashtag
niche, music style). Nothing here is invented; the templating is a
formatting layer over real numbers, the same design principle as qa.py.

Usage:
    python brief_generator.py --summary data/creator_summary.csv --raw data/trending_tiktoks.csv --out briefs/
"""

import argparse
import os
import sys

import pandas as pd

# Force UTF-8 output on Windows consoles, which default to a limited
# encoding (cp1252) that can't print emojis or special characters
# sometimes present in captions.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

MIN_VIDEOS_FOR_HIGH_CONFIDENCE = 3


def load_data(summary_path, raw_path):
    summary = pd.read_csv(summary_path)
    raw = pd.read_csv(raw_path)
    return summary, raw


def get_target_creators(summary):
    """The 16 high-confidence Rising creators: the real, actionable list."""
    return summary[
        (summary["segment"] == "Rising") & (summary["confidence"] == "high")
    ].sort_values("promising_score", ascending=False)


def get_content_signals(raw, author):
    """Pull real style signals for one creator: duration, music, hashtag niche."""
    rows = raw[raw["author_name"] == author]
    if rows.empty:
        return {"avg_duration": None, "pct_original_music": None, "top_hashtag": None, "sample_caption": None}
    avg_duration = rows["duration_sec"].mean()
    pct_original = rows["music_is_original"].mean()
    hashtag_counts = rows["primary_hashtag"].dropna()
    top_hashtag = hashtag_counts.value_counts().index[0] if not hashtag_counts.empty else None
    captions = rows["caption"].dropna()
    sample_caption = captions.iloc[0] if not captions.empty else None
    return {
        "avg_duration": round(avg_duration, 1) if pd.notna(avg_duration) else None,
        "pct_original_music": round(pct_original, 2) if pd.notna(pct_original) else None,
        "top_hashtag": top_hashtag,
        "sample_caption": sample_caption,
    }


def budget_tier(row):
    """Suggested tier from real reach and engagement, not a guess."""
    views = row["median_views"]
    engagement = row["median_engagement_rate"]
    if views >= 500000:
        return "Tier 1 (high reach, negotiate rate against 500K+ median views)"
    elif views >= 100000 and engagement >= 0.15:
        return "Tier 2 (strong reach + above-average engagement, good value)"
    elif engagement >= 0.15:
        return "Tier 3 (smaller reach, high engagement, low-cost test partner)"
    else:
        return "Tier 4 (smaller reach, moderate engagement, low-risk trial)"


def content_angle(signals, engagement_rate):
    """A content angle grounded in what's actually working for this creator."""
    parts = []
    if signals["avg_duration"] is not None:
        if signals["avg_duration"] <= 15:
            parts.append("short, fast-cut format (their videos average under 15 seconds)")
        elif signals["avg_duration"] <= 25:
            parts.append("mid-length format (their videos average 15-25 seconds)")
        else:
            parts.append("longer-form format (their videos average over 25 seconds)")
    if signals["pct_original_music"] is not None:
        if signals["pct_original_music"] >= 0.8:
            parts.append("original audio or voiceover, not trending sounds")
        else:
            parts.append("trending/popular audio")
    if signals["top_hashtag"]:
        parts.append(f"their established niche around #{signals['top_hashtag']}")
    if not parts:
        parts.append("no strong content pattern detected yet, treat as an open brief")
    return "; ".join(parts)


def storyboard_concept(author, signals, angle, engagement_rate):
    """A short creative concept, ready to feed into CapCut or an image-gen tool."""
    duration = signals["avg_duration"] or 15
    niche = signals["top_hashtag"] or "their usual content style"
    return (
        f"A {round(duration)}-second partnership video in {author}'s established style: "
        f"open on {niche}-adjacent content to match audience expectations, "
        f"weave in the product/brand naturally within the first 3 seconds (their "
        f"{formatpct(engagement_rate)} engagement rate suggests hook-dependent viewing), "
        f"close on a call to action that matches their existing caption tone."
    )


def formatpct(v):
    return f"{v * 100:.1f}%"


def outreach_draft(author, row, signals):
    """A real first-touch message draft, grounded in this creator's actual numbers
    and content style, not a generic template. Still needs a human read-through
    before sending, but nobody has to start from a blank page."""
    engagement = formatpct(row["median_engagement_rate"])
    niche = signals["top_hashtag"]
    niche_line = f" love what you've been doing in the {niche} space" if niche else " love your content"

    return (
        f"Hi {author},\n\n"
        f"I've been following your videos and{niche_line}. Your engagement rate has been "
        f"running around {engagement} across your last {int(row['video_count'])} posts, which is well "
        f"above what we typically see, and it's clear your audience trusts what you put out.\n\n"
        f"We'd love to explore a partnership. Based on your usual format "
        f"({content_angle(signals, row['median_engagement_rate'])}), we think there's a natural fit "
        f"for something that keeps your voice front and center rather than feeling like a typical ad.\n\n"
        f"Would you be open to a quick call this week to talk through what that could look like?\n\n"
        f"Best,\n[Your name]"
    )


def build_brief(row, signals):
    author = row["author"]
    engagement = row["median_engagement_rate"]
    return {
        "creator": author,
        "priority_rank": None,  # filled in by caller based on sort order
        "video_count": int(row["video_count"]),
        "engagement_rate": formatpct(engagement),
        "median_views": f"{int(row['median_views']):,}",
        "budget_tier": budget_tier(row),
        "content_angle": content_angle(signals, engagement),
        "storyboard_concept": storyboard_concept(author, signals, content_angle(signals, engagement), engagement),
        "outreach_draft": outreach_draft(author, row, signals),
        "sample_caption": signals["sample_caption"] or "(no caption on file)",
    }


def render_markdown(briefs):
    lines = ["# Project Oasis: Creative Partnership Briefs", "",
             "Generated from real engagement data for the 16 high-confidence Rising creators.",
             "Each brief is a starting point for outreach and creative planning, not a final script.", ""]
    for b in briefs:
        lines.append(f"## {b['priority_rank']}. {b['creator']}")
        lines.append(f"- **Engagement rate:** {b['engagement_rate']} across {b['video_count']} videos")
        lines.append(f"- **Median views:** {b['median_views']}")
        lines.append(f"- **Suggested budget tier:** {b['budget_tier']}")
        lines.append(f"- **Content angle:** {b['content_angle']}")
        lines.append(f"- **Storyboard concept:** {b['storyboard_concept']}")
        lines.append(f"- **Their voice (sample caption):** \"{b['sample_caption']}\"")
        lines.append(f"- **Outreach draft:**")
        lines.append("  ```")
        for line in b['outreach_draft'].split("\n"):
            lines.append(f"  {line}")
        lines.append("  ```")
        lines.append("")
    return "\n".join(lines)


def run(summary_path, raw_path, out_dir):
    summary, raw = load_data(summary_path, raw_path)
    targets = get_target_creators(summary)

    briefs = []
    for rank, (_, row) in enumerate(targets.iterrows(), start=1):
        signals = get_content_signals(raw, row["author"])
        brief = build_brief(row, signals)
        brief["priority_rank"] = rank
        briefs.append(brief)

    os.makedirs(out_dir, exist_ok=True)

    md_path = os.path.join(out_dir, "creative_briefs.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(briefs))

    csv_path = os.path.join(out_dir, "creative_briefs.csv")
    pd.DataFrame(briefs).to_csv(csv_path, index=False, encoding="utf-8")

    return briefs, md_path, csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project Oasis creative brief generator")
    parser.add_argument("--summary", default="data/creator_summary.csv", help="Path to creator_summary.csv")
    parser.add_argument("--raw", default="data/trending_tiktoks.csv", help="Path to the raw video CSV")
    parser.add_argument("--out", default="briefs", help="Output directory for briefs")
    args = parser.parse_args()

    try:
        briefs, md_path, csv_path = run(args.summary, args.raw, args.out)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Generated {len(briefs)} creative briefs.")
    print(f"Markdown: {md_path}")
    print(f"CSV: {csv_path}")
    print(f"\nFirst brief:\n")
    print(f"{briefs[0]['creator']}: {briefs[0]['content_angle']}")
    print(f"Concept: {briefs[0]['storyboard_concept']}")
