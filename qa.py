"""
Project Oasis: Q&A layer over the creator summary table.

Lets someone ask plain-English questions about the creator data and get
answers grounded in real numbers. The LLM never generates stats itself.
It only picks a function from a fixed set, and reports what that function
actually returned. See data_flow.md for the full design rationale.

Usage:
    export ANTHROPIC_API_KEY=your_key_here
    python qa.py [--data data/creator_summary.csv]

Then ask questions like:
    "who are the top rising creators?"
    "tell me about creator bundaddy"
    "what does undervalued mean?"
    "which creators have engagement over 15% and aren't verified?"
"""

import argparse
import json
import os
import sys

import pandas as pd

try:
    import anthropic
except ImportError:
    print(
        "This script needs the anthropic package. Install it with:\n"
        "    pip install anthropic",
        file=sys.stderr,
    )
    sys.exit(1)

MODEL = "claude-sonnet-4-6"

DEFINITIONS = {
    "promising": (
        "A creator with consistent, above-average engagement across multiple "
        "videos, who isn't yet operating at mega-scale. One-video outliers are "
        "excluded, and verified or high-view accounts are down-weighted, since "
        "those are already discovered and likely more expensive to sign."
    ),
    "rising": "Strong, consistent engagement, not yet mega-scale. The primary target list.",
    "proven": "Strong engagement plus verified or high views. A reach play, but costlier.",
    "breakout": "One viral outlier, inconsistent otherwise. Worth watching, not yet worth betting on.",
    "confidence": (
        "How many videos a creator's score is based on. Low confidence at "
        "1 video, medium at 2, high at 3 or more. A single lucky post "
        "shouldn't be mistaken for a pattern."
    ),
    "undervalued": (
        "Creators getting outsized engagement relative to how few people "
        "have seen them yet, measured as engagement_rate / views."
    ),
}


# ---------------------------------------------------------------------------
# Fixed set of functions the LLM is allowed to call. It picks one, this
# script runs it against the real table, and only the returned data goes
# back into the answer.
# ---------------------------------------------------------------------------

def get_top_creators(df, segment=None, metric="promising_score", n=10):
    subset = df if not segment else df[df["segment"].str.lower() == segment.lower()]
    if metric not in df.columns:
        metric = "promising_score"
    subset = subset.sort_values(metric, ascending=False).head(n)
    return subset[["author", "segment", "confidence", "median_engagement_rate",
                    "median_views", "promising_score"]].to_dict(orient="records")


def get_creator_stats(df, name):
    match = df[df["author"].str.lower() == str(name).lower()]
    if match.empty:
        return {"error": f"No creator named '{name}' found in the dataset."}
    return match.iloc[0].to_dict()


def compare_segments(df):
    return (
        df.groupby("segment")
        .agg(
            creator_count=("author", "count"),
            median_engagement_rate=("median_engagement_rate", "median"),
            median_views=("median_views", "median"),
        )
        .reset_index()
        .to_dict(orient="records")
    )


def explain_definition(df, term):
    key = str(term).lower().strip()
    if key in DEFINITIONS:
        return {"term": key, "definition": DEFINITIONS[key]}
    return {"error": f"No definition on file for '{term}'.", "available_terms": list(DEFINITIONS.keys())}


def search_creators(df, min_engagement=None, verified=None, segment=None, n=20):
    subset = df.copy()
    if min_engagement is not None:
        subset = subset[subset["median_engagement_rate"] >= min_engagement]
    if verified is not None:
        subset = subset[subset["author_verified"] == verified]
    if segment is not None:
        subset = subset[subset["segment"].str.lower() == segment.lower()]
    subset = subset.sort_values("promising_score", ascending=False).head(n)
    return subset[["author", "segment", "confidence", "median_engagement_rate",
                    "author_verified"]].to_dict(orient="records")


def get_most_undervalued(df, n=5):
    subset = df.sort_values("median_efficiency", ascending=False).head(n)
    return subset[["author", "median_engagement_rate", "median_views",
                    "median_efficiency", "confidence"]].to_dict(orient="records")


FUNCTIONS = {
    "get_top_creators": get_top_creators,
    "get_creator_stats": get_creator_stats,
    "compare_segments": compare_segments,
    "explain_definition": explain_definition,
    "search_creators": search_creators,
    "get_most_undervalued": get_most_undervalued,
}

# ---------------------------------------------------------------------------
# Tool schemas: what the LLM sees when deciding which function to call.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_top_creators",
        "description": "Get the top N creators ranked by a metric, optionally filtered to one segment (Rising, Proven, Breakout, Other).",
        "input_schema": {
            "type": "object",
            "properties": {
                "segment": {"type": "string", "description": "Rising, Proven, Breakout, or Other. Omit for all segments."},
                "metric": {"type": "string", "description": "Column to sort by. Defaults to promising_score."},
                "n": {"type": "integer", "description": "How many creators to return. Defaults to 10."},
            },
        },
    },
    {
        "name": "get_creator_stats",
        "description": "Get full stats for one named creator.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "The creator's author handle."}},
            "required": ["name"],
        },
    },
    {
        "name": "compare_segments",
        "description": "Get creator count and median stats broken down by segment (Rising, Proven, Breakout, Other).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "explain_definition",
        "description": "Explain what a term means in this analysis, e.g. 'promising', 'rising', 'confidence', 'undervalued'.",
        "input_schema": {
            "type": "object",
            "properties": {"term": {"type": "string", "description": "The term to define."}},
            "required": ["term"],
        },
    },
    {
        "name": "search_creators",
        "description": "Search creators by minimum engagement rate, verified status, and/or segment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "min_engagement": {"type": "number", "description": "Minimum median engagement rate, as a decimal (e.g. 0.1 for 10%)."},
                "verified": {"type": "boolean", "description": "True to require verified, False to require non-verified. Omit for either."},
                "segment": {"type": "string", "description": "Rising, Proven, Breakout, or Other. Omit for any."},
                "n": {"type": "integer", "description": "Max results to return. Defaults to 20."},
            },
        },
    },
    {
        "name": "get_most_undervalued",
        "description": "Get the N creators with the highest efficiency score (engagement relative to how few views they've gotten).",
        "input_schema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "How many creators to return. Defaults to 5."}},
        },
    },
]

SYSTEM_PROMPT = """You are the Q&A layer for Project Oasis, a tool that helps a Head of
Creator Partnerships find promising TikTok creators from a precomputed dataset.

Rules you must follow:
- Never invent or estimate numbers. Every statistic in your answer must come
  from a tool result, not from your general knowledge of TikTok or creators.
- Always call exactly one tool before answering a data question.
- If a question can't be answered by any available tool, say plainly that
  it's not something you can determine from this dataset. Do not guess.
- When a creator has low or medium confidence, mention that explicitly so
  the person doesn't mistake a thin sample for a proven pattern.
- Keep answers short and plain-English. This is for a non-technical reader.
"""


def ask(client, df, question):
    messages = [{"role": "user", "content": question}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

    if not tool_use_blocks:
        # No tool called, just return the model's direct text (e.g. it decided
        # the question is out of scope).
        text_blocks = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_blocks)

    messages.append({"role": "assistant", "content": response.content})

    tool_results = []
    for block in tool_use_blocks:
        func = FUNCTIONS.get(block.name)
        if func is None:
            result = {"error": f"Unknown function: {block.name}"}
        else:
            try:
                result = func(df, **block.input)
            except Exception as e:
                result = {"error": str(e)}
        tool_results.append(
            {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, default=str)}
        )

    messages.append({"role": "user", "content": tool_results})

    final = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    text_blocks = [b.text for b in final.content if b.type == "text"]
    return "\n".join(text_blocks)


def main():
    parser = argparse.ArgumentParser(description="Project Oasis Q&A")
    parser.add_argument("--data", default="data/creator_summary.csv", help="Path to creator_summary.csv")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: set the ANTHROPIC_API_KEY environment variable first.", file=sys.stderr)
        sys.exit(1)

    try:
        df = pd.read_csv(args.data)
    except FileNotFoundError:
        print(
            f"Error: couldn't find {args.data}. Run analysis.py first to generate it.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = anthropic.Anthropic()

    print("Project Oasis Q&A. Ask a question about the creators, or type 'quit'.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in ("quit", "exit"):
            break
        try:
            answer = ask(client, df, question)
        except Exception as e:
            answer = f"Something went wrong: {e}"
        print(f"\n{answer}\n")


if __name__ == "__main__":
    main()
