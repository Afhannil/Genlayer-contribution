# TranslationQualityRegistry

A reusable GenLayer Intelligent Contract primitive for on-chain, consensus-verified
translation quality assessment — usable by open-source i18n projects, subtitle
crowdsourcing platforms, or any community translation workflow that needs a
neutral, tamper-resistant quality oracle.

**Deployed contract (GenLayer Studio):** `0xA7...16e0` (full address in Studio Explorer)

## Why this is a primitive, not a thin demo

- **Dual web-fetch, cross-lingual consensus**: validators independently fetch
  both the source document and the translated document via `gl.nondet.web.render`,
  then judge semantic equivalence between two texts in two different languages.
- **Structured consensus with wording tolerance**: validators agree on
  `(status, issues)` via `gl.eq_principle.prompt_comparative`.
- **Single-use contest per review**: each review (`task_id:revision_number`) can
  be contested exactly once. A second contest attempt on the same review reverts
  with `"this review has already been contested"`, preventing repeated retries
  aimed at fishing for a favorable outcome and ensuring reputation updates
  exactly once per eligible contest.
- **A correctly defined "overturn"**: status quality is explicitly ranked
  (`inaccurate` < `minor_issues` < `accurate`). A contest only counts as
  `overturned: true` when the new verdict ranks strictly better than the prior
  one — a replacement verdict that is the same or worse is never credited as a
  successful overturn, even though the label technically differs from the prior
  status.
- **No non-deterministic wall-clock state**: the contract does not persist any
  `time.time()`-based or otherwise non-deterministic timestamp. All records are
  ordered and referenced purely by `task_id` and `revision_number`.

## State design

| Field         | Type                | Purpose                                                    |
|----------------|---------------------|----------------------------------------------------------------|
| `owner`        | `str`               | Platform/admin address                                       |
| `tasks`        | `TreeMap[str, str]` | task_id -> JSON {source_url, source_lang, target_lang, status, revision_count} |
| `reviews`      | `TreeMap[str, str]` | "task_id:revision_number" -> JSON review record               |
| `disputes`     | `TreeMap[str, str]` | "task_id:revision_number" -> JSON dispute record (presence = already contested) |
| `reputation`   | `TreeMap[str, str]` | address -> JSON {upheld, overturned}                          |

## How consensus, single-contest enforcement, and overturn ranking work together

```python
STATUS_RANK = {"inaccurate": 0, "minor_issues": 1, "accurate": 2}

@gl.public.write
def contest_status(self, task_id: str, contester_argument: str) -> None:
    ...
    review_key = f"{task_id}:{current_revision - 1}"
    assert review_key not in self.disputes, "this review has already been contested"
    ...
    agreed = json.loads(agreed_raw)
    overturned = STATUS_RANK[agreed["status"]] > STATUS_RANK[prior["status"]]
    ...
    self.disputes[review_key] = json.dumps({...})
```

1. `submit_translation` fetches both documents, prompts an LLM to judge
   translation fidelity, and reaches consensus on `{status, issues}` via
   `gl.eq_principle.prompt_comparative`.
2. `contest_status` first checks `review_key not in self.disputes` — since the
   dispute record for a review is only ever written once, this guarantees each
   review is contestable exactly once, and reputation logic (which only runs
   after this check passes) updates exactly once per eligible contest.
3. The re-evaluation re-fetches both documents independently and reaches a
   fresh consensus verdict.
4. `overturned` is computed by comparing `STATUS_RANK` of the new verdict
   against the prior one — strictly greater means genuinely improved, which is
   the only case credited as a successful overturn.

## Verified on-chain test evidence

| Test | Tx | Result |
|---|---|---|
| Deploy (fixed contract) | `0x7b4a32d83796acc657696f8825013a609cc5c80f8d5dbb38482a3b8a4131de92` | SUCCESS |
| `post_task` (tt1) | `0x34b1d61ff24293eb84d4440ea502bea7ee243ee58b75daa4d7b8186e2bc91365` | SUCCESS |
| `submit_translation` (tt1) — inaccurate case | `0xc3aa619e5cba12f670eb5baa97f4821ea7864ede0f905d82d2062e951c1d514e` | SUCCESS — `status: "inaccurate"` |
| `contest_status` (tt1) — first contest | `0xb57d4581529927baaacf3a2909a05f370ad10c97d25ddb73aefa7c3d049c52ef` | SUCCESS — verdict re-evaluated, remained `"inaccurate"` |
| `contest_status` (tt1) — second contest attempt on the same review | `0xc3d68e7d148bbb7d7e2cfe802c4a81c2ecd1af89390e9a17e5527b7862da277c` | ERROR: `this review has already been contested` |

`get_dispute("tt1", 0)` after the first contest:
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
`overturned: false` is correctly computed here: the new status did not rank
higher than the prior status (both `"inaccurate"`, `STATUS_RANK` equal), so no
credit is given for a non-improving replacement verdict — directly addressing
the requirement that a worse or equal replacement verdict must not be credited
as a successful overturn.

Full test narrative in [TESTS.md](./TESTS.md).

## Suggested tests to reproduce (GenLayer Studio)

- Deploy, `post_task`, submit a clearly inaccurate translation.
- Contest once — confirm it succeeds and `get_dispute` shows a result.
- Contest the same review again — confirm it reverts with
  `"this review has already been contested"`.
- Submit a translation that goes from `inaccurate` to a contest producing an
  `accurate` or `minor_issues` re-evaluation — confirm `overturned: true` only
  in this genuinely-improved case.
- Confirm no method call ever raises an `AttributeError` related to timestamps.

## Caveats

- GenLayer's exact SDK surface (`gl.nondet.web.render`, `gl.eq_principle.*`,
  `gl.message.*`) is evolving — verify current method names/signatures against
  GenLayer's latest docs before deploying.
- Without any persisted timestamp, downstream consumers needing chronological
  ordering of tasks/reviews should rely on `revision_count` and external
  indexing (e.g., block height at transaction time) rather than in-contract
  time data.
