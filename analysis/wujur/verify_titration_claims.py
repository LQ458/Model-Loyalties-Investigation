#!/usr/bin/env python3
"""Guard the numeric claims in titration_status.md against titration_recovered.json.

Rationale (DataRestore, adopted): a guard is a claim, and an UNEXERCISED guard is an
unverified claim. Neither reading the regex nor observing a pass is evidence that it
checks anything -- only a deliberate mutation that makes it fail is. So this ships with
`--mutation-test`, which injects known-wrong values and asserts each one is caught.

Two layers, because pattern-matching alone has a blind spot that bit both agents on this
project: a pattern whose phrasing does not match the target sentence SKIPS it silently and
still reports a clean pass.

  Layer 1 CLAIM CHECK    every matched numeric claim must equal the artifact value.
  Layer 2 COVERAGE CHECK every unquoted occurrence of a guarded noun must fall inside some
                         matched claim span. An unattributed occurrence is a violation even
                         if no claim disagrees, because it means the guard is not looking
                         at it.

Quote-aware: in-line retractions legitimately quote superseded numbers, so text inside
double quotes is exempt from both layers.

Usage:
    python3 analysis/wujur/verify_titration_claims.py
    python3 analysis/wujur/verify_titration_claims.py --mutation-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPORT = HERE / "titration_status.md"
ARTIFACT = HERE / "titration_recovered.json"

WORDS = {"zero": 0, "one": 1, "once": 1, "two": 2, "twice": 2, "three": 3, "four": 4,
         "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty-one": 21}

# Design note. v1 of this guard was PHRASE-anchored: it enumerated verb phrasings
# ("hence N changes", "changed N times"). That has the blind spot that bit both agents on
# this project -- a sentence phrased any other way ("means three changes") is SKIPPED
# silently and the guard still reports a clean pass. v2 is NOUN-anchored instead: find
# every place a guarded noun is preceded by a number, whatever the surrounding phrasing.
# Coverage is then automatic rather than a second layer, because every number-adjacent
# mention is examined by construction.
#
# QUALIFIER absorbs bold markers and words legitimately sitting between number and noun
# ("four distinct `N` constructions", "three separate changes").
# REPEATABLE, because real phrases stack qualifiers: "four distinct `N` constructions"
# needs both `distinct` and `` `N` `` absorbed. A single optional slot silently failed to
# capture that exact sentence -- the same blind-spot class this guard exists to catch.
_QWORD = r"(?:distinct|separate|further|earlier|earliest|later|such|other|contiguous|N)"
QUALIFIER = r"(?:(?:\*\*|__|`)*" + _QWORD + r"?(?:\*\*|__|`)*\s*){0,3}"

# NO EXEMPTIONS. An earlier version exempted "the two earliest constructions" as a subset
# phrase. Per DataRestore, subset claims are CHECKABLE if you compute the subset, and an
# exemption is a phrase pin -- the very thing this guard replaces. So the subset now has a
# DERIVED spec (total minus the pre-pad and current constructions) and is compared, not
# silenced. Specs are ordered specific-before-general and consume their spans, so the
# general `constructions` spec does not re-flag a span the subset spec already checked.
EXEMPT_SUBSET: dict[str, str] = {}


def _artifact() -> dict[str, Any]:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def claim_specs(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """noun -> expected integer. The noun is what anchors the search."""
    ev = doc["n_cell_length_evidence"]
    return [
        # specific first: "the two earliest constructions" = total minus pre-pad minus current
        {"label": "earliest_constructions_subset", "noun": r"earliest\s+constructions",
         "expect": ev["n_construction_count"] - 2},
        {"label": "constructions", "noun": r"constructions",
         "expect": ev["n_construction_count"]},
        {"label": "changes", "noun": r"changes",
         "expect": ev["n_construction_transitions"]},
        {"label": "transitions", "noun": r"transitions",
         "expect": ev["n_construction_transitions"]},
        {"label": "prepad_dirs", "noun": r"directories in total",
         "expect": ev["n_runs_sharing_prepad_N"]},
        {"label": "generations_files", "noun": r"`generations\.jsonl`",
         "expect": doc["user_privilege_scan"]["n_generation_files_scanned"]},
        {"label": "f7_keys", "noun": r"top-level\s+keys",
         "expect": len(doc["reproduction"]["F7_privilege"]["keys_compared"])},
        {"label": "parseable_rows", "noun": r"parseable\s+rows",
         "expect": doc["bounds"]["observed_s_range"]["n_parseable_rows"]},
    ]


def strip_quoted(md: str) -> str:
    """Blank out double-quoted spans so in-line retractions may quote wrong numbers."""
    return re.sub(r'"[^"\n]{0,120}"', lambda m: '"' + "~" * (len(m.group(0)) - 2) + '"', md)


def to_int(tok: str) -> int | None:
    tok = tok.strip("*`_ ").lower()
    if tok.isdigit():
        return int(tok)
    return WORDS.get(tok)


def verify(md: str, doc: dict[str, Any]) -> dict[str, Any]:
    body = strip_quoted(md)
    violations: list[str] = []
    found: dict[str, list[int]] = {}
    examined: dict[str, int] = {}

    consumed: list[tuple[int, int]] = []
    for spec in claim_specs(doc):
        vals: list[int] = []
        captured: list[tuple[int, int]] = []
        # token before the noun, tolerating bold markers on EITHER side of the number
        # ("**83** parseable rows") as well as qualifier words between the two.
        pat = r"([\w\-]+)(?:\*\*|__|`)*\s+" + QUALIFIER + spec["noun"]
        mentions = list(re.finditer(spec["noun"], body, re.IGNORECASE))
        for m in re.finditer(pat, body, re.IGNORECASE):
            v = to_int(m.group(1))
            if v is None:
                continue  # not a numeric claim (e.g. "scorer changes"), correctly ignored
            # whitespace-normalised: markdown wraps lines, so an exempt phrase can be
            # split by a newline ("two earliest\nconstructions").
            if any(m.start() < e and s0 < m.end() for s0, e in consumed):
                continue  # a more specific spec already checked this span
            captured.append((m.start(), m.end()))
            consumed.append((m.start(), m.end()))
            vals.append(v)
            if v != spec["expect"]:
                ctx = re.sub(r"\s+", " ", body[max(0, m.start() - 50):m.end() + 30]).strip()
                violations.append(
                    f"CLAIM {spec['label']}: prose says {v}, artifact says "
                    f"{spec['expect']} -- ...{ctx}...")
        # MISSED-CLAIM detection. This is the failure mode that produced a clean pass on
        # an unchecked sentence twice on this project: the noun is mentioned WITH a number
        # nearby, but the pattern did not capture it, so nothing was compared. A number in
        # the 30 chars before an uncaptured mention means the guard is not looking.
        for mm in mentions:
            if any(s0 <= mm.start() < e for s0, e in captured + consumed):
                continue
            # sentence-bounded, last 3 tokens only. A wider window produced false
            # positives from unrelated numerals ("Phase 2. Constructions must be...",
            # "the one where the recovery changes...").
            lookback = body[max(0, mm.start() - 90):mm.start()]
            # split on markdown emphasis and dashes as well as sentence punctuation:
            # "...not four.** Count constructions..." must not glue across the marker.
            lookback = re.split(r"[.:;!?\n|]|\*\*|—|--", lookback)[-1]
            toks = re.findall(r"[\w\-]+", lookback)[-3:]
            ctx_after = body[mm.start():mm.end() + 4]
            if any(to_int(t) is not None for t in toks):
                ctx = re.sub(r"\s+", " ", body[max(0, mm.start() - 60):mm.end() + 20]).strip()
                violations.append(
                    f"MISSED-CLAIM {spec['label']}: a number sits beside an uncaptured "
                    f"mention, so nothing was compared -- ...{ctx}...")
        found[spec["label"]] = vals
        examined[spec["label"]] = len(mentions)

    return {"found": found, "violations": violations, "noun_mentions": examined,
            "expect": {s["label"]: s["expect"] for s in claim_specs(doc)}}


# Each mutation declares the violation KIND it must produce.
# Asserting the kind is not pedantry: if captured spans were recorded as match END offsets
# rather than full spans (DataRestore hit exactly this), a mutated CAPTURED claim would be
# reported as MISSED-CLAIM instead of CLAIM. Checking only "some violation fired" would
# pass while the layer silently mis-attributed every claim.
MUTATIONS: list[tuple[str, str, str, str]] = [
    ("constructions count", "CLAIM",
     "four distinct `N` constructions", "five distinct `N` constructions"),
    ("changes count, 'hence' form", "CLAIM", "hence three changes", "hence seven changes"),
    ("changes count, 'means' form", "CLAIM",
     "four distinct constructions means three changes", "four distinct constructions means eight changes"),
    ("bare phrasing, no qualifier", "CLAIM",
     "The correct statement:", "The morning holds nine constructions. The correct statement:"),
    # anchor must target the UNQUOTED instance: an earlier version of this entry matched the
    # first occurrence in the file, which sits inside double quotes and is therefore stripped
    # before checking, so the mutation was silently ineffective and the suite reported a miss.
    ("derived subset count", "CLAIM",
     "bucketing the two earliest constructions", "bucketing the six earliest constructions"),
    ("prepad directory count", "CLAIM", "five directories in total", "nine directories in total"),
    ("f7 key count", "CLAIM", "all 15 top-level keys", "all 21 top-level keys"),
    ("digit form", "CLAIM", "hence three changes", "hence 7 changes"),
    ("parseable row count", "CLAIM", "83** parseable rows", "91** parseable rows"),
    # the case only the noun/missed-claim layer can catch: a number sits in the clause but
    # in a phrasing the capture pattern cannot attribute, so nothing would be compared.
    ("unattributable adjacency", "MISSED-CLAIM",
     "The correct statement:", "Roughly 9 or so constructions appear. The correct statement:"),
]


def coverage(md: str, doc: dict[str, Any]) -> dict[str, Any]:
    """Measure and check the guard's own scope, so the report cannot overstate it.

    Design point, DataRestore's: the DENOMINATOR is a self-referential fixpoint -- it moves
    every time the prose is edited, including by the sentence that states it. An exact
    figure would need chasing on every revision, and a number that needs chasing will
    eventually be wrong. So the report is required to make a FLOOR claim on mentions and a
    CEILING claim on the covered fraction, both stable under ordinary editing. Only the
    noun count, which is controlled in this file, is asserted exactly.
    """
    body = strip_quoted(md)
    nocode = re.sub(r"```.*?```", "", body, flags=re.S)
    digits = re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])", nocode)
    words = [w for w in re.findall(r"\b[a-z]+\b", nocode.lower()) if w in WORDS]
    mentions = len(digits) + len(words)
    res = verify(md, doc)
    n_claims = sum(len(v) for v in res["found"].values())
    n_nouns = len(res["expect"])
    frac = n_claims / mentions if mentions else 0.0

    problems: list[str] = []
    # All three scope patterns are whitespace-tolerant. A single-space version failed
    # because markdown wrapped "more than\n**600**" across a line -- the THIRD place in
    # this file where line wrapping defeated a pattern. Assume it everywhere.
    m_nouns = re.search(r"guards\s+\*\*(\d+)\s+nouns\*\*", md)
    if not m_nouns:
        problems.append("report does not state the guarded-noun count in the expected form")
    elif int(m_nouns.group(1)) != n_nouns:
        problems.append(f"report says {m_nouns.group(1)} guarded nouns, actual {n_nouns}")

    m_floor = re.search(r"more\s+than\s+\*\*(\d+)\*\*\s+numeric\s+mentions", md)
    if not m_floor:
        problems.append("report does not state a FLOOR on numeric mentions")
    elif mentions < int(m_floor.group(1)):
        problems.append(f"report floor {m_floor.group(1)} exceeds actual mentions {mentions}")

    m_ceil = re.search(r"under\s+\*\*(\d+(?:\.\d+)?)%\*\*\s+of", md)
    if not m_ceil:
        problems.append("report does not state a CEILING on covered fraction")
    elif frac * 100.0 > float(m_ceil.group(1)):
        problems.append(f"covered fraction {frac*100:.2f}% exceeds stated ceiling {m_ceil.group(1)}%")

    return {"guarded_nouns": n_nouns, "claims_compared": n_claims,
            "numeric_mentions": mentions, "covered_fraction": round(frac, 4),
            "problems": problems}


# Mutations for the SCOPE check itself. Exercising coverage() out-of-band in a shell was
# the same mistake this file exists to correct: an unexercised guard is an unverified claim,
# and a guard exercised only in a scrollback is an unverifiable one. Committed here.
SCOPE_MUTATIONS: list[tuple[str, str, str]] = [
    ("floor too high", "more than **600** numeric mentions", "more than **9000** numeric mentions"),
    ("ceiling too tight", "under **3%** of them", "under **0.1%** of them"),
    ("wrong noun count", "guards **8 nouns**", "guards **4 nouns**"),
    ("floor removed", "more than **600** numeric mentions", "a good many numeric mentions"),
    ("ceiling removed", "under **3%** of them", "a small share of them"),
]


def mutation_test(md: str, doc: dict[str, Any]) -> int:
    print("MUTATION TEST -- each injected error MUST produce at least one violation\n")
    base = verify(md, doc)
    if base["violations"]:
        print("  ABORT: baseline already violating; fix the report first")
        for v in base["violations"]:
            print("    " + v)
        return 1
    print("  baseline: 0 violations (clean)\n")
    failures = []
    for name, kind, old, new in MUTATIONS:
        # anchors are whitespace-tolerant: markdown wraps lines, so a literal-substring
        # anchor silently SKIPS when the phrase happens to straddle a newline -- which is
        # itself the "guard reports clean on something it never examined" failure mode.
        rx = re.compile(r"\s+".join(re.escape(t) for t in old.split()))
        m = rx.search(md)
        if not m:
            print(f"  {'SKIP':7s} {name}: anchor absent -- {old!r}")
            failures.append(name)
            continue
        mutated = md[:m.start()] + new + md[m.end():]
        res = verify(mutated, doc)
        kinds = {v.split(":")[0].split()[0] for v in res["violations"]}
        ok = bool(res["violations"]) and kind in kinds
        print(f"  {'FIRED' if ok else 'MISSED':7s} {name}: {len(res['violations'])} violation(s), "
              f"kinds={sorted(kinds) or '-'}, required={kind}")
        if res["violations"]:
            print(f"          {res['violations'][0][:130]}")
        if not ok:
            failures.append(f"{name} (wanted {kind}, got {sorted(kinds) or 'nothing'})")
    print()
    if failures:
        print(f"GUARD IS INCOMPLETE -- {len(failures)} mutation(s) not caught: {failures}")
        return 1
    print("SCOPE MUTATIONS -- each must produce at least one scope problem\n")
    for name, old, new in SCOPE_MUTATIONS:
        rx = re.compile(r"\s+".join(re.escape(t) for t in old.split()))
        m = rx.search(md)
        if not m:
            print(f"  {'SKIP':7s} {name}: anchor absent -- {old!r}")
            failures.append(name)
            continue
        cov = coverage(md[:m.start()] + new + md[m.end():], doc)
        ok = bool(cov["problems"])
        print(f"  {'FIRED' if ok else 'MISSED':7s} {name}: {cov['problems'] or 'nothing'}")
        if not ok:
            failures.append(name)
    print()
    if failures:
        print(f"GUARD IS INCOMPLETE -- not caught: {failures}")
        return 1
    print(f"GUARD EXERCISED -- all {len(MUTATIONS)} claim mutations and "
          f"{len(SCOPE_MUTATIONS)} scope mutations caught")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutation-test", action="store_true")
    args = ap.parse_args()
    md = REPORT.read_text(encoding="utf-8")
    doc = _artifact()
    if args.mutation_test:
        return mutation_test(md, doc)
    cov = coverage(md, doc)
    print("guard scope:", json.dumps({k: v for k, v in cov.items() if k != "problems"}))
    for pr in cov["problems"]:
        print("  SCOPE PROBLEM: " + pr)
    res = verify(md, doc)
    print("artifact expectations:", json.dumps(res["expect"]))
    print("numeric claims found:", json.dumps(res["found"]))
    print("noun mentions seen  :", json.dumps(res["noun_mentions"]))
    if res["violations"] or cov["problems"]:
        print(f"\n{len(res['violations'])} VIOLATION(S), {len(cov['problems'])} SCOPE PROBLEM(S):")
        for v in res["violations"] + cov["problems"]:
            print("  " + v)
        return 1
    print("\n0 violations, 0 scope problems")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
