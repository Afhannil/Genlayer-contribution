# TranslationQualityRegistry

A reusable GenLayer Intelligent Contract primitive for on-chain, consensus-verified
translation quality assessment — usable by open-source i18n projects, subtitle
crowdsourcing platforms, or any community translation workflow that needs a
neutral, tamper-resistant quality oracle.

## Why this is a primitive, not a thin demo

- **Dual web-fetch, cross-lingual consensus**: unlike a single-document check,
  validators independently fetch *both* the source document and the translated
  document via `gl.nondet.web.render`, then judge semantic equivalence between
  two texts in two different languages — a genuinely different consensus
  challenge from rule-matching against a policy or a criteria checklist. This
  exercises GenLayer's multilingual reasoning together with its internet-access
  capability.
- **Structured, closed-vocabulary consensus with wording tolerance**: validators
  must agree on `(status, issues)` via `gl.eq_principle.prompt_comparative`, with
  an explicit principle: `status` must match exactly, while `issues` wording can
  vary as long as it refers to the same underlying translation problem. This
  matches how real bilingual reviewers actually agree — same verdict, possibly
  different phrasing of the same issue.
- **Revision lifecycle**: `revision_count` and per-revision review records let a
  translation go through multiple rounds — reviewer flags an issue, translator
  fixes it, resubmits — mirroring real community translation workflows.
- **Independent dispute round**: `contest_status` re-fetches both documents and
  re-runs the full bilingual comparison from scratch with the translator's
  counter-argument injected, rather than trusting the original result or simply
  re-running the same prompt. Reputation counters (`upheld` / `overturned`) track
  contest outcomes per address.
- **Narrowly scoped and reusable**: the contract only produces a verifiable
  on-chain quality verdict; it doesn't dictate payment, workflow, or platform UX,
  so any translation marketplace or open-source project can build on top of it.

## State design

| Field         | Type                | Purpose                                                    |
|----------------|---------------------|----------------------------------------------------------------|
| `owner`        | `str`               | Platform/admin address                                       |
| `tasks`        | `TreeMap[str, str]` | task_id -> JSON {source_url, source_lang, target_lang, status, revision_count} |
| `reviews`      | `TreeMap[str, str]` | "task_id:revision_number" -> JSON review record               |
| `disputes`     | `TreeMap[str, str]` | task_id -> JSON dispute record                                |
| `reputation`   | `TreeMap[str, str]` | address -> JSON {upheld, overturned}                          |

## How consensus is used

1. `submit_translation` builds a closure that (a) fetches the source URL, (b)
   fetches the translated URL, (c) prompts an LLM to judge whether the
   translation accurately, completely, and naturally conveys the source's
   meaning, returning `{status, issues}`.
2. `gl.eq_principle.prompt_comparative` re-runs this closure across validators
   and only accepts the result once they agree under the stated principle —
   independent fetches of both documents and independent bilingual LLM
   judgments converge on the same structured verdict.
3. `contest_status` repeats the same dual-fetch, bilingual-comparison pattern
   with the translator's counter-argument injected, producing a fresh,
   independent consensus result rather than deferring to the original one.

```python
def get_verdict() -> str:
    source_text = gl.nondet.web.render(source_url, mode="text")
    translated_text = gl.nondet.web.render(translated_url, mode="text")
    prompt = self._review_prompt(source_text, translated_text, source_lang, target_lang)
    raw = gl.nondet.exec_prompt(prompt, response_format="json")
    return json.dumps(self._normalize_verdict(raw), sort_keys=True)

agreed = gl.eq_principle.prompt_comparative(
    get_verdict,
    principle="status must be exactly the same; issues may differ in wording "
              "only if they refer to the same underlying translation problem."
)
```

## Suggested tests (GenLayer Studio)

- **Deploy**, then `post_task` with a real source document URL, `source_lang`
  (e.g. "English"), `target_lang` (e.g. "Spanish").
- **Accurate case**: submit a URL with a genuinely faithful translation, assert
  `status == "accurate"` and `issues == []`.
- **Inaccurate case**: submit a URL with a deliberately wrong/unrelated
  translation, assert `status == "inaccurate"` and `issues` non-empty.
- **Minor issues + revision**: submit a mostly-correct but imperfect translation,
  assert `status == "minor_issues"`, `revision_count` increments; then resubmit
  an improved translation and assert `status == "accurate"`.
- **Contest — dismissed**: contest a correctly-flagged inaccurate translation
  with a weak argument, assert `overturned == False` and reputation `upheld`
  increments.
- **Contest — overturned**: contest with a genuinely better translation URL,
  assert `overturned == True` is possible when justified.
- **Duplicate task guard**: assert `post_task` reverts if `task_id` already
  exists.

## Caveats

- GenLayer's exact SDK surface (`gl.nondet.web.render`, `gl.eq_principle.*`,
  `gl.message.*`) is evolving — verify current method names/signatures against
  GenLayer's latest docs before deploying.
- `gl.nondet.web.render` requires both URLs to be publicly reachable;
  private/auth-gated URLs won't work without an extension to this pattern.
- Translation quality judgment quality depends on the underlying LLM's fluency
  in both languages — for low-resource language pairs, validator agreement may
  be harder to reach; this is an inherent property of the domain, not a bug in
  the consensus design.
- No token transfer logic is included (by design, and because GenLayer Studio
  does not currently support token transfers) — pairing this with an escrow or
  bounty contract that reads `get_task(task_id).status` is a natural extension.
