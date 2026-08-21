# Project Oasis: Summary

## What "promising" means here
A creator with consistent, above-average engagement across multiple videos,
who isn't yet operating at mega-scale. One-video outliers are excluded, and
verified or high-view accounts are down-weighted, since those are already
discovered and likely more expensive to sign.

## The dataset
1,000 trending videos, 802 creators, a 3-month window from September to
December 2020. 89% of creators appear only once in this data, so most
scores rest on a thin sample. The 16 creators below are the exception:
they show up 3 or more times, so their numbers reflect a real pattern,
not a lucky post.

## Top Rising creators (high confidence, 3+ videos)
| Creator | Videos | Engagement rate | Median views |
|---|---|---|---|
| bundaddy | 5 | 23.0% | 99,900 |
| xaaku | 3 | 21.2% | 143,700 |
| erinwilliams_1 | 3 | 19.4% | 309,000 |
| chris_wells_ | 3 | 19.2% | 64,400 |
| liamkratos | 3 | 18.4% | 62,100 |
| papaswolio | 4 | 16.7% | 266,600 |
| jadeanna_ | 3 | 14.7% | 598,200 |
| maxzg7 | 3 | 14.5% | 188,400 |

Full list of 16 in `creator_summary.csv`, filtered to segment = Rising and
confidence = high.

## Most Undervalued
Creators getting outsized engagement relative to how few people have seen
them yet.

| Creator | Engagement rate | Median views | Confidence |
|---|---|---|---|
| anwarali0125 | 49.7% | 943 | low |
| zohaib_ali05 | 31.9% | 977 | low |

Both are low confidence, based on a single video. Worth a manual look
before treating either as a real lead, since a number this high on this
few views can also mean an anomalous post rather than a pattern.

## Segment breakdown
| Segment | Creators | Median engagement rate |
|---|---|---|
| Rising | 361 | 13.1% |
| Proven | 40 | 12.7% |
| Breakout | 39 | 5.2% |
| Other | 362 | 5.4% |

## Caveats worth stating out loud
- This is a 2020 snapshot, not live data. None of these are current leads.
- No follower count exists in the data, so "reach" means views, not audience size.
- The broader 361-creator Rising list includes many single-video creators.
  Treat those as leads to watch, not confirmed bets. The 16 high-confidence
  names above are the ones to lead with.
