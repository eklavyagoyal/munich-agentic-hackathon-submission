# Insurance Invoice Poker — challenge brief

Verbatim from the QuantCo challenge listing (screenshot, 2026-08-22). Kept separate
from [GAME_DESCRIPTION.md](../GAME_DESCRIPTION.md) (the handout with the actual rules)
and [the slides](quantco-claim-to-fame-slides.md), because **the three disagree** — see
"Contradictions" below.

> A leaderboard game against the other teams. Every 15 minutes each team gets an
> insurance claim and has to make a bid.
>
> Insurance runs on a quiet negotiation: a tradesperson writes an invoice, an insurer
> decides what it's actually worth. Both sides are guessing what the other will accept.
>
> Here you play both roles at once. Each round brings a new policy, a new damage report,
> and a blank invoice. You set what you charge and what you're willing to pay when that
> same bill lands on your desk from another team.
>
> Charge too much and you get rejected. Pay too much and you've been had. Every round is
> a read on your opponents, and all results are public afterwards.
>
> **Bill high, pay low. Best margin wins.**

**Prize: 1000 €.**

## Judging criteria

**What you built**

| Criterion | Wording | What it means for us |
| --- | --- | --- |
| Score | "Where you finished. The main signal, **not the only one**" | Winning the leaderboard is necessary but not sufficient. |
| Generality | "Also works on completely new policies" | Argues directly against overfitting the price book. An unseen trade or policy must degrade gracefully, not collapse. The LLM path and the abstain-then-fall-back ladder are the answer to this criterion. |
| Consistency | "**The more rounds it plays cleanly, the better**" | Reliability is judged, not just assumed. A missed or defaulted round costs twice: the `1.5a` penalties *and* this score. |

**How you pitch it**

- Clarity — "If we can't follow it, we can't credit it"
- Problem — "What's hard about pricing a claim from both sides"
- Approach — "The strategy you went in with, **and how it changed as you played**"
- Solution — "What you ended up with, and the logic behind it"

The Approach criterion rewards a visible change of mind. The event log and the
calibration loop are what let us show one with evidence rather than assert it.

## Contradictions between the three sources

| | Round cadence | Prize |
| --- | --- | --- |
| Slides (`quantco-claim-to-fame-slides.md`) | "New case released every 10 minutes" | AirPods Pro 3 + 100 € credit per person |
| This challenge listing | "Every 15 minutes" | 1000 € |
| **Leaderboard API (authoritative)** | **757.576 s = 12 min 37.6 s** | — |

**Do not hardcode a cadence.** The live schedule is published per game; see
[leaderboard-api.md](leaderboard-api.md). Anything built on "every 10 minutes" drifts
out of sync within a few rounds.

The prize difference is probably the general hackathon prize versus the challenge
prize. Worth one question to the organisers, not worth a decision.
