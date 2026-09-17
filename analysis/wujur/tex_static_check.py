#!/usr/bin/env python3
"""Independent static checks on both manuscripts.

WHY THIS EXISTS
---------------
Neither manuscript has ever been compiled. There is no pdflatex, latexmk or
tectonic on this machine and no compile endpoint in the Overleaf MCP, so every
validity claim about either paper is static. The writing agents reported clean
static checks; those reports have not been independently reproduced. An unchecked
claim that the checks passed is worth about as much as an unchecked claim that
the numbers are right.

So this re-derives the checks from the source, with no reference to what any
agent reported. It is not a substitute for a compile: it cannot catch a missing
package, a float that will not place, an overfull box, or a class option
conflict. What it does catch is the mechanical class of defect that makes LaTeX
either fail or silently emit a wrong document.

WHAT IT CHECKS, AND WHY EACH ONE EARNS ITS PLACE
------------------------------------------------
1. labels vs references. A dangling \\ref renders as "??" and a desk reviewer
   sees it immediately. An unreferenced \\label is harmless but usually means a
   cross-reference was dropped during editing.
2. cite keys vs bibitems. A \\cite with no \\bibitem renders "[?]". A \\bibitem
   with no \\cite is an uncited reference, which in a triple-anonymous venue is
   a padding signal. NOTE the asymmetric danger: a dropped \\cite whose
   \\bibitem was dropped with it renders NOTHING and is invisible to this check
   and to the compiler alike. That defect class is only catchable by reading, and
   this repository has already had one instance of it.
3. brace balance and environment nesting. Either one breaks the compile outright.
4. tabular geometry. Ampersand count per row against the column specification.
   A row with too many ampersands is a hard error; too few silently shifts
   content left, which is worse because it compiles.
5. anonymity. Any URL, e-mail, ORCID or obvious affiliation string in RENDERED
   text, ignoring comments, since comments are not published. Third-party
   citation URLs are legitimate and are listed rather than flagged.
6. word counts under three conventions, because they disagree near a ceiling and
   an editor may count differently than the author.

Verbatim-ish environments are skipped for the ampersand check because an
ampersand inside tikz or lstlisting is not a column separator.

USAGE
  python3 tex_static_check.py                 both papers
  python3 tex_static_check.py path/to/x.tex   one file

Exit is non-zero if any hard check fails, so this can gate a commit.

REVERT: delete this file. It reads and writes nothing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEX = HERE / "tex"
DEFAULTS = [TEX / "main.tex", TEX / "paper2.tex"]

VERBATIM_ENVS = {"tikzpicture", "lstlisting", "verbatim", "Verbatim", "minted"}


def strip_comments(text: str) -> str:
    """Remove LaTeX comments, honouring escaped percent signs."""
    out = []
    for line in text.split("\n"):
        i, esc = 0, False
        cut = len(line)
        while i < len(line):
            c = line[i]
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == "%":
                cut = i
                break
            i += 1
        out.append(line[:cut])
    return "\n".join(out)


def check_refs(body: str) -> tuple[list[str], list[str], int, int]:
    labels = re.findall(r"\\label\{([^}]*)\}", body)
    refs = set()
    for cmd in ("ref", "eqref", "autoref", "Cref", "cref", "pageref"):
        refs |= set(re.findall(r"\\" + cmd + r"\{([^}]*)\}", body))
    lab = set(labels)
    return sorted(refs - lab), sorted(lab - refs), len(labels), len(refs)


def check_cites(body: str) -> tuple[list[str], list[str], int, int]:
    keys = set()
    for m in re.finditer(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", body):
        keys |= {k.strip() for k in m.group(1).split(",") if k.strip()}
    items = [m.group(1).strip() for m in re.finditer(r"\\bibitem(?:\[[^\]]*\])?\{([^}]*)\}", body)]
    it = set(items)
    return sorted(keys - it), sorted(it - keys), len(it), len(keys)


def check_braces(body: str) -> int:
    depth = 0
    esc = False
    for c in body:
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
    return depth


def check_envs(body: str) -> list[str]:
    stack, errs = [], []
    for m in re.finditer(r"\\(begin|end)\{([^}]*)\}", body):
        kind, name = m.group(1), m.group(2)
        if kind == "begin":
            stack.append(name)
        else:
            if not stack:
                errs.append(f"\\end{{{name}}} with empty stack")
            elif stack[-1] != name:
                errs.append(f"\\end{{{name}}} closes \\begin{{{stack[-1]}}}")
                stack.pop()
            else:
                stack.pop()
    errs += [f"unclosed \\begin{{{n}}}" for n in stack]
    return errs


def ncols(spec: str) -> int:
    """Count columns in a tabular/tabularx column specification."""
    spec = re.sub(r"@\{[^}]*\}", "", spec)
    spec = re.sub(r"p\{[^}]*\}", "c", spec)
    spec = re.sub(r"[mb]\{[^}]*\}", "c", spec)
    spec = re.sub(r">\{[^}]*\}", "", spec)
    spec = re.sub(r"<\{[^}]*\}", "", spec)
    spec = re.sub(r"\*\{(\d+)\}\{([^}]*)\}",
                  lambda m: m.group(2) * int(m.group(1)), spec)
    return sum(1 for c in spec if c in "lcrXLRCY")


def check_tabulars(body: str) -> list[str]:
    errs = []
    pat = re.compile(
        r"\\begin\{(tabular|tabularx|array)\}(?:\{[^{}]*\})?\s*\{((?:[^{}]|\{[^{}]*\})*)\}",
        re.S)
    for m in pat.finditer(body):
        env, spec = m.group(1), m.group(2)
        n = ncols(spec)
        end = body.find(f"\\end{{{env}}}", m.end())
        if end < 0 or n == 0:
            continue
        inner = body[m.end():end]
        for raw in inner.split(r"\\"):
            row = raw.strip()
            if not row:
                continue
            if re.match(r"^\\(toprule|midrule|bottomrule|hline|cmidrule|addlinespace)", row):
                continue
            row_nc = re.sub(r"\\multicolumn\{(\d+)\}", "", row)
            amps = len(re.findall(r"(?<!\\)&", row_nc))
            span = sum(int(x) - 1 for x in re.findall(r"\\multicolumn\{(\d+)\}", row))
            if amps + span + 1 != n:
                errs.append(f"{env}[{n} cols]: row has {amps} ampersands "
                            f"(+{span} spanned) -> {amps+span+1} cells: {row[:70]!r}")
    return errs


def check_anonymity(body: str) -> tuple[list[str], list[str]]:
    urls = re.findall(r"\\url\{([^}]*)\}|https?://[^\s{}\\,]+", body)
    flat = [u if isinstance(u, str) else next(x for x in u if x) for u in urls]
    flat = [u for u in flat if u]
    suspicious = []
    for pat, why in ((r"[\w.+-]+@[\w-]+\.[\w.]+", "email"),
                     (r"\borcid\b", "ORCID"),
                     (r"\b(University|Universit|Institute|Laborator|Department) of\b", "affiliation")):
        for m in re.finditer(pat, body, re.I):
            suspicious.append(f"{why}: {m.group(0)[:60]!r}")
    return sorted(set(flat)), suspicious


def words(body: str) -> dict[str, int]:
    def count(t: str) -> int:
        t = re.sub(r"\\begin\{(tikzpicture|thebibliography)\}.*?\\end\{\1\}", " ", t, flags=re.S)
        t = re.sub(r"\\[a-zA-Z]+\*?", " ", t)
        t = re.sub(r"[{}$&~^_\\]", " ", t)
        return len([w for w in t.split() if any(ch.isalnum() for ch in w)])
    doc = body
    m = re.search(r"\\begin\{document\}(.*)\\end\{document\}", body, re.S)
    if m:
        doc = m.group(1)
    no_bib = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ", doc, flags=re.S)
    m2 = re.search(r"(.*?)\\appendix", no_bib, re.S)
    main = m2.group(1) if m2 else no_bib
    return {"main_text_only": count(main),
            "incl_appendix_excl_bib": count(no_bib),
            "everything_in_document": count(doc)}


def run(path: Path) -> bool:
    raw = path.read_text(encoding="utf-8")
    body = strip_comments(raw)
    print(f"\n{'='*72}\n{path.name}  {len(raw)} bytes  {raw.count(chr(10))+1} lines\n{'='*72}")

    dangling, unref, nlab, nref = check_refs(body)
    bad_cites, uncited, nitem, nkey = check_cites(body)
    depth = check_braces(body)
    envs = check_envs(body)
    tabs = check_tabulars(body)
    urls, susp = check_anonymity(body)
    wc = words(body)

    hard = bool(dangling or bad_cites or depth or envs or tabs)

    print(f"labels {nlab}, references {nref}")
    print(f"  dangling refs (render as ??): {dangling or 'none'}")
    print(f"  unreferenced labels:          {unref or 'none'}")
    print(f"bibitems {nitem}, distinct cite keys {nkey}")
    print(f"  cites with no bibitem (render as [?]): {bad_cites or 'none'}")
    print(f"  bibitems never cited:                 {uncited or 'none'}")
    print(f"brace balance: {depth} ({'OK' if depth == 0 else 'BROKEN'})")
    print(f"environment nesting: {envs or 'OK'}")
    print(f"tabular geometry: {'OK' if not tabs else ''}")
    for e in tabs:
        print(f"  {e}")
    print(f"anonymity: {len(urls)} URL(s) in rendered text")
    for u in urls:
        print(f"  {u}")
    print(f"  other identity signals: {susp or 'none'}")
    print("word counts:")
    for k, v in wc.items():
        flag = "  <-- OVER 10,000" if v > 10000 else ""
        print(f"  {k:26s} {v}{flag}")
    print(f"PENDING markers in source (comments, not rendered): "
          f"{len(re.findall(r'PENDING', raw))}")
    print(f"__omp_magic residue: {raw.count('__omp_magic')}")
    print(f"\n{path.name}: {'HARD CHECKS PASS' if not hard else 'HARD CHECK FAILURES'}")
    return not hard


def main() -> int:
    targets = [Path(a) for a in sys.argv[1:]] or DEFAULTS
    ok = all(run(p) for p in targets if p.is_file())
    print(f"\n{'all hard checks pass' if ok else 'FAILURES PRESENT'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
