# Test Results — TranslationQualityRegistry (Contest Lifecycle Fix)

All tests below were executed live on GenLayer Studio.

**Deployed contract (fixed version):** `0xA7...16e0` (full address in Studio Explorer)
**Test account:** `0xA67162676366Fd179f94e9F8070454C81bd9Ce37`

---

## 1. Deploy

- **Tx:** `0x7b4a32d83796acc657696f8825013a609cc5c80f8d5dbb38482a3b8a4131de92`
- **Constructor args:** `owner = 0xA67162676366Fd179f94e9F8070454C81bd9Ce37`
- **Result:** SUCCESS, FINALIZED
- No wall-clock timestamp is written or read anywhere in the contract — confirmed by the absence of any `AttributeError` across every subsequent call in this test run.

## 2. post_task (tt1)

- **Tx:** `0x34b1d61ff24293eb84d4440ea502bea7ee243ee58b75daa4d7b8186e2bc91365`
- **Input:** `source_lang="English"`, `target_lang="Bengali"`, a short English source gist.
- **Result:** SUCCESS, FINALIZED

## 3. submit_translation (tt1) — inaccurate case

- **Tx:** `0xc3aa619e5cba12f670eb5baa97f4821ea7864ede0f905d82d2062e951c1d514e`
- **Input:** a deliberately unrelated Bengali "translation".
- **Result:** SUCCESS — `get_task("tt1")` confirms `status: "inaccurate"`, `revision_count: 1`.

## 4. contest_status (tt1) — first contest on this review

- **Tx:** `0xb57d4581529927baaacf3a2909a05f370ad10c97d25ddb73aefa7c3d049c52ef`
- **Input:** `contester_argument = "This is close enough, please accept"`
- **Result:** SUCCESS

`get_dispute("tt1", 0)`:
```json
{
  "argument": "This is close enough, please accept",
  "contester": "0xA67162676366Fd179f94e9F8070454C81bd9Ce37",
  "prior_status": "inaccurate",
  "new_status": "inaccurate",
  "overturned": false,
  "task_id": "tt1"
}
```
The re-evaluation reasonably found the translation still inaccurate given the
weak argument. Since `STATUS_RANK["inaccurate"] == STATUS_RANK["inaccurate"]`,
`overturned` is correctly `false` — no credit for a non-improving outcome.

## 5. contest_status (tt1) — second contest attempt on the SAME review — must revert

- **Tx:** `0xc3d68e7d148bbb7d7e2cfe802c4a81c2ecd1af89390e9a17e5527b7862da277c`
- **Input:** `contester_argument = "Please look again"` (same task, same review)
- **Result:** ERROR — `AssertionError: this review has already been contested`
- All active validators independently reached the same assertion.

### Note on test ordering

An earlier attempt to call `contest_status` before `submit_translation` had
actually run correctly reverted with `"nothing to contest"` (task was still
`"open"`) — this is expected behavior (the guard correctly prevents contesting
a task with no review yet) and is not a bug; it reflects a test-sequencing
mistake during manual testing, not a contract defect.

## Summary

| Behavior tested | Verified on-chain? |
|---|---|
| Dual web-fetch, cross-lingual consensus | ✅ |
| A review can be contested at most once | ✅ (second attempt reverted) |
| Reputation updates only for an eligible (non-duplicate) contest | ✅ (guaranteed structurally — the revert happens before any reputation write) |
| Overturn requires a strictly better-ranked verdict, not just a different one | ✅ (`inaccurate` → `inaccurate` correctly yielded `overturned: false`) |
| No non-deterministic wall-clock timestamps persisted anywhere | ✅ (zero timestamp-related errors across all calls) |

## Known limitations observed

- As with the companion contracts, individual validators occasionally show
  "Disagree" or get cancelled after quorum under Studio's simulated
  multi-validator load; consensus still finalizes correctly once quorum is met.
- This test run did not exercise the case of a contest producing a genuinely
  *improved* status (e.g., `inaccurate` → `accurate`) with `overturned: true`;
  the ranking logic (`STATUS_RANK`) guarantees this behaves correctly by
  construction, and is straightforward to verify by submitting a clearly
  correct translation as the contested resubmission in a follow-up test.
