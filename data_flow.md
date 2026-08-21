# Project Oasis: Data Flow

How a question turns into an answer.

```
Question (plain English)
      |
      v
[Intent check]: is this answerable from our data, or out of scope?
      |
      v
[Function selection]: LLM picks from a fixed set of functions:
      get_top_creators(segment, metric, n)
      get_creator_stats(name)
      compare_segments()
      explain_definition()
      search_creators(min_engagement, verified, segment)
      get_most_undervalued(n)
      |
      v
[Function runs against the precomputed creator summary table]
      (includes engagement_rate, consistency, efficiency, confidence flag)
      |
      v
[Structured result]: numbers, creator names, segment and confidence labels
      |
      v
[LLM formatting pass]: plain-English answer, citing real numbers,
      flags low-confidence creators explicitly if relevant
      |
      v
Answer (shown to user, source numbers traceable)
```

## Design principle
The LLM selects a function and reports what that function actually returned
from the precomputed creator table. Every answer traces back to a real number
in the data, which is what keeps the tool trustworthy for a non-technical reader.

## Accuracy and trust notes
- **The model looks things up.** Every answer is generated from a real,
  precomputed table of creator stats.
- **Every number is traceable.** If the tool says "Creator X has a 6%
  engagement rate," that number came directly from the data and can be
  checked against the summary table.
- **The model explains its definition, not just its answer.** Any time it
  references "promising," it restates what that means in this context, so
  there's no hidden judgment call.
- **If the data can't answer a question, the tool says so,** rather than
  producing a plausible-sounding but unsupported response.
