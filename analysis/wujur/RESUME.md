# RESUME — paused 2026-09-17, agent idle for 2 hours by request

Credits are tight. The agent is paused; the machine keeps working. This file is
the handoff so the next turn costs nothing in rediscovery.

## Running without supervision

`wujur-runs-detached` (hub process, **detached**, pid 98901) runs
`analysis/wujur/run_queue.sh`. Detached so it survives omp exiting and the
terminal closing, which the previous non-persistent launch would not have.

| Run | State at pause | Target |
| --- | --- | --- |
| `f_phase1_k3ext_20260916` | **COMPLETE, 120/120, 0 http errors, 1 unparseable** | done |
| `f7r_userpriv_k3_20260916` (Block A) | starting | 36 rows, ~25 min |

Both resumable. The queue re-enters where it stopped; Block A re-clears its
36/36 hash gate before spending any generation, so an interrupted restart cannot
produce off-spec prompts.

## Result that landed before the pause

kappa at six item clusters, `analysis/wujur/kappa_6item.json`, scored against
the plan frozen in `prereg_amendment_stimulus_set.md` §5 before any row was read.

| Stratum | items | kappa | 95% CI | margin from 0 | sign determined |
| --- | --- | --- | --- | --- | --- |
| frozen (published) | 2 | -0.2716763005780347 | [-0.6134969325153373, -0.01556420233463037] | 2.60% | no |
| new | 4 | -0.7131931166347992 | [-0.9384035197988686, -0.43726474278544547] | 87.25% | yes |
| **pooled (primary)** | **6** | **-0.5667731629392972** | **[-0.8037880400085124, -0.30457578646329836]** | **61.01%** | **yes** |

Outcome **A** under the pre-committed labelling: last-wins supported at six
clusters, same sign as the published estimate. The 5% margin override does not
fire (61% >> 5%). Heterogeneity check: frozen and new intervals overlap, so
pooled is designated primary, as the plan specifies.

All four gates pass in all three strata. `D = s_P - s_M` is 0.8650 / 0.8717 /
0.8694 and `s_N` is -0.0 in every stratum, so the four new domains measure the
same quantity as the frozen two. That is what licenses the pooling.

## First three actions on resume

1. `python3 analysis/wujur/score_block_a.py --run --workers 8` if the queue has
   not finished it, else it is already scored. Then read
   `analysis/wujur/block_a_corrected.json`.
   **Watch the fork:** `kappa_priv = -0.895 / D_user`, in range only if
   `D_user >= 0.895`. Gate G3's 0.4 threshold is nowhere near sufficient. If
   `D_user < 0.895`, G5 FAILS and that failure is substantive - super-additive
   amplification - and must NOT be renormalised again. Both branches are
   pre-labelled; neither may be chosen after seeing the number.
2. Commit `kappa_6item.json` and `block_a_corrected.json` with the numbers in
   the message. 22 commits currently on `wujur-2026-fall`, pushed, `main`
   untouched at `4b5d4b2`.
3. Resume `Paper2Writer` with both results. Its abstract currently discloses the
   2-cluster fragility as its second sentence, quantified; that disclosure is now
   **obsolete** and must be replaced by the 6-cluster result rather than merely
   softened. The order-sensitivity claim can now be inferential.

## Paper 1 state

Done pending compile. `analysis/wujur/tex/main.tex`, sha256
`4d85175fb2fed58d4bc3ff38bfe379cc73caa9df25750cd01b84bb85b04e0df7`,
86,620 bytes, mirror byte-identical to the Overleaf remote.

Round 5 closed out a blind critic's NOT READY: both blockers fixed, 13 majors
and 15 minors applied, 2 critic findings rejected with reasons, and one defect
the critic missed (Table 12 mixing Wilson with exact intervals) found and fixed.

**Word count is the binding constraint: 9,917 against the 10,000 ceiling, 83
words of headroom.** The next substantive addition forces a table to
supplementary. Do not trim argument to make space.

## Two operational hazards

- **Before any Overleaf write, delete `/tmp/overleaf-6a66c67ec9ea4e40ef9efe64`.**
  The MCP write path clones into it unconditionally and FAILS if it exists.
- `mcp__overleaf_read_file` truncates in the returned payload, not just the
  display. Never hash or mirror what it returns. Use the clone, or this repo's
  `analysis/wujur/tex/` mirror.

## Still only Barry can do this

Compile `main.tex` in the Overleaf UI, two passes. No TeX engine on this box and
no compile endpoint in the MCP. It is also the only check that catches a dropped
citation whose bibitem went with it, since that renders no `[?]`.
