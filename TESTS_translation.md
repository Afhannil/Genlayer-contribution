# Test Results — TranslationQualityRegistry

All tests below were executed live on GenLayer Studio (not simulated locally).

**Deployed contract:** `0x02...40C5` (see GenLayer Studio Explorer for full address)
**Network:** GenLayer Studio (studionet)
**Test account:** `0xA67162676366Fd179f94e9F8070454C81bd9Ce37`

---

## 1. Deploy

- **Tx:** `0x0b758740bf2662ef8dc0cfd1c43627da41921d4365120984bc10a44ae74e858a`
- **Result:** SUCCESS, FINALIZED

## 2. post_task — task t2 (English source, Bengali target)

- **Tx:** `0x9ec8d6e9d9a5ef2c3196dee6700f77906f227c02934304786b1fb19225611342`
- **Input:** `source_url` → a short English gist ("GenLayer is a blockchain platform. It uses AI validators to reach consensus. Smart contracts can access the internet directly."), `source_lang="English"`, `target_lang="Bengali"`

## 3. submit_translation — accurate case

- **Tx:** `0xa8a470c2f4daa4dd4a574b37643d7e98536f5a2a892aa34398bb35689f9b8785`
- **Input:** a genuine, faithful Bengali translation of the source text

`get_review("t2", 0)`:
```json
{
  "status": "accurate",
  "issues": [],
  "revision_number": 0
}
```
Validators independently fetched both the English source and the Bengali translation and agreed the translation was faithful.

## 4. submit_translation — inaccurate case (task t4, cross-checked with a deliberately unrelated translation)

- **post_task tx:** `0x777d674df562de3abcd7451444bcff37c23dc30c7e013cb631e5029a253c6b3f`
- **submit_translation tx:** `0xd19d8f8306ecbabf6ac5f9d899ceedc7da0a5d7e264d18dd0b24895f60f36670`
- **Input:** the same English source, but a Bengali "translation" about an unrelated topic (favorite food, weekly market trips)

`get_review("t4", 0)`:
```json
{
  "status": "inaccurate",
  "issues": [
    "completely unrelated translation content",
    "source meaning about blockchain platform is missing",
    "no mention of AI validators or consensus mechanism",
    "smart contracts and internet access not translated",
    "translation discusses personal food preferences instead"
  ]
}
```
Validators didn't just flag the mismatch — they identified five specific, substantive reasons, showing genuine bilingual comprehension rather than a surface-level check (e.g. length or keyword matching).

## 5. contest_status — dismissed case

- **Tx:** `0x11ae1f759aef59e5ee6e73f25d21ddb33aee7534209d1ce7004ce8b20079d0e0`
- **Input:** `contester_argument = "This is actually a reasonable translation, please reconsider and accept it."`

`get_dispute("t4")`:
```json
{
  "prior_status": "inaccurate",
  "new_status": "inaccurate",
  "overturned": false
}
```
`get_reputation("0xA67162676366Fd179f94e9F8070454C81bd9Ce37")`:
```json
{"upheld": 1, "overturned": 0}
```
The contest re-ran the full dual-fetch bilingual comparison independently and correctly dismissed a weak, unsupported argument rather than deferring to it.

## Summary

| Behavior tested | Verified on-chain? |
|---|---|
| Dual web-fetch consensus (source + translation) | ✅ |
| Structured `(status, issues)` consensus via `prompt_comparative` | ✅ |
| Accurate translation correctly recognized | ✅ |
| Inaccurate translation correctly rejected with specific reasons | ✅ |
| Contest produces a fresh, independent consensus round | ✅ |
| Contest correctly dismissed when argument doesn't hold up | ✅ |
| Reputation counters update on contest outcome | ✅ |

## Known limitations observed

- One `submit_translation` call against a long, complex source document (a full project README rather than a short paragraph) resulted in repeated "Majority disagreement, rotating the leader" events and ultimately an `UNDETERMINED` consensus result (validators could not agree, e.g. some judged "accurate" vs "minor_issues"). Retrying with a shorter, less ambiguous source document resolved this. This suggests translation-quality judgments on long or nuanced documents may need either a stricter grading rubric or a larger validator pool to reliably converge — a useful finding for anyone building on this primitive with longer documents.
- As with the companion contracts, individual validators can occasionally time out on LLM calls under Studio's simulated multi-validator load; consensus still finalizes once quorum is met.
- One Studio RPC call (`gen_getContractSchemaForCode`) intermittently returned an `invalid_contract absent_runner_comment` error mid-session; this did not affect any actual contract transaction, all of which finalized successfully (aside from the UNDETERMINED case above, which was a genuine validator disagreement, not an RPC error).
