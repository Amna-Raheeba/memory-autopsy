# Experiment log

## 2026-11-17 — first evaluation run (seed 7, 250 traces)

Headline numbers looked good (decisive recovery 1.000) but three
verdict classes were not perfect:

| Verdict | Precision | Recall | Cause |
|---|---|---|---|
| contradicted | 0.60 | 1.00 | Cross-episode leakage (see below) |
| helpful | 1.00 | 0.65 | Same records, mislabelled as contradicted |
| misleading | 1.00 | 0.71 | Same records, mislabelled as contradicted |
| unresolved | 1.00 | 0.58 | Same records, mislabelled as contradicted |
| poisoned | 0.94 | 1.00 | Stale-truth poisoning (see below) |

## Bug 1 — contradiction leaked across episodes

**Symptom.** 194 false-positive `contradicted` verdicts. A record
written in one decision's episode was labelled contradicted because
a leftover record from an *earlier* episode disagreed with it — the
two were never read together.

**Root cause.** The verdict asked "is this record part of any live
contradiction pair?" — a store-wide question. The store accumulates
parallel versions across decisions, so in a long trace almost every
record eventually has a live disagreeing cousin.

**Fix.** Scope contradictions to one decision
(`store.contradiction_partners`): a record is `contradicted` only
when its conflicting partner was read by the *same* decision. The
blame graph keeps the store-wide `contradicts` edges (the structural
view), but the verdict is about what the agent saw. After the fix:
contradicted P/R 1.000, helpful R 0.996, misleading R 1.000,
unresolved R 1.000.

## Bug 2 — poison's structural clause used stale truth

**Symptom.** 19 false-positive `poisoned` verdicts, all the
untrusted-but-correct edge-case records in mixed traces: an untrusted
record holding the current true value was called poisoned for
contradicting an earlier trusted record whose value was once correct
but no longer is.

**Root cause.** `contradicts_trusted` accepted any trusted record
whose value matched *any* labelled decision's `correct_value` — a
value that was correct two episodes ago counted as truth.

**Fix.** The trusted partner must hold the value the *latest*
labelled decision confirms as correct for the key. After the fix:
poisoned P/R 1.000, helpful R 1.000. Remaining honest limit: the
structural clause is only as current as the latest label; an unread
poison record planted after the last label, contradicting a record
whose truth is unlabelled, is missed.

## After the fixes

Seed 7: every verdict class with instances P = R = 1.000; decisive
recovery 1.000 (1,350/1,350). Seeds 1, 42, 123: identical — no
imperfect verdict class on any seed (1,000 traces total). The
aggregate rates (stale-read 0.1249, poison-influence 0.3179,
contradiction 0.2156, redundant 0.1163) were unchanged by both fixes:
they count trace facts, not verdicts.
