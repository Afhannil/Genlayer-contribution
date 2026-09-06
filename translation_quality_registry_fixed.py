# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json


STATUSES = ("accurate", "minor_issues", "inaccurate")
STATUS_RANK = {"inaccurate": 0, "minor_issues": 1, "accurate": 2}


class TranslationQualityRegistry(gl.Contract):
    owner: str
    tasks: TreeMap[str, str]
    reviews: TreeMap[str, str]
    disputes: TreeMap[str, str]
    reputation: TreeMap[str, str]

    def __init__(self, owner: str):
        self.owner = owner
        self.tasks = TreeMap()
        self.reviews = TreeMap()
        self.disputes = TreeMap()
        self.reputation = TreeMap()

    def _sender(self) -> str:
        return str(gl.message.sender_address)

    def _normalize_verdict(self, parsed: dict) -> dict:
        status = str(parsed.get("status", "")).strip().lower()
        if status not in STATUSES:
            status = "minor_issues"
        issues = parsed.get("issues", [])
        if not isinstance(issues, list):
            issues = []
        issues = [str(i) for i in issues]
        if status == "accurate":
            issues = []
        return {"status": status, "issues": issues}

    def _review_prompt(self, source_text: str, translated_text: str,
                        source_lang: str, target_lang: str, extra: str = "") -> str:
        return f"""
You are a bilingual translation quality reviewer. Compare the SOURCE text
(in {source_lang}) against the TRANSLATION (in {target_lang}). Judge whether
the translation accurately, completely, and naturally conveys the meaning of
the source. Return ONLY JSON with exactly these keys:
{{"status":"accurate","issues":[],"summary":"short reason"}}

status must be one of: accurate, minor_issues, inaccurate
issues must list specific problems (mistranslations, omissions, added content,
tone/register mismatches) found, each as a short phrase
accurate = faithful and complete translation
minor_issues = mostly correct but has small errors, awkward phrasing, or minor omissions
inaccurate = meaning is significantly wrong, missing, or misleading

{extra}

SOURCE ({source_lang}):
\"\"\"{source_text}\"\"\"

TRANSLATION ({target_lang}):
\"\"\"{translated_text}\"\"\"
""".strip()

    def _agree_verdict(self, prompt: str) -> dict:
        def get_verdict() -> str:
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(self._normalize_verdict(raw), sort_keys=True)

        agreed_raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            principle=(
                "status must be exactly the same. "
                "issues may differ in wording only if they refer to the same "
                "underlying translation problem; the set of distinct issues "
                "identified must be substantively the same."
            ),
        )
        return json.loads(agreed_raw)

    @gl.public.write
    def post_task(self, task_id: str, source_url: str, source_lang: str, target_lang: str) -> None:
        assert task_id not in self.tasks, "task already exists"
        record = {
            "source_url": source_url,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "status": "open",
            "revision_count": 0,
        }
        self.tasks[task_id] = json.dumps(record)

    @gl.public.view
    def get_task(self, task_id: str) -> dict:
        assert task_id in self.tasks, "no such task"
        return json.loads(self.tasks[task_id])

    @gl.public.view
    def debug_has_task(self, task_id: str) -> bool:
        return task_id in self.tasks

    @gl.public.write
    def submit_translation(self, task_id: str, translated_url: str) -> None:
        assert task_id in self.tasks, "no such task"
        task = json.loads(self.tasks[task_id])
        assert task["status"] in ("open", "minor_issues", "inaccurate"), "task not accepting submissions"

        source_url = task["source_url"]
        source_lang = task["source_lang"]
        target_lang = task["target_lang"]

        def get_verdict() -> str:
            source_text = gl.nondet.web.render(source_url, mode="text")
            translated_text = gl.nondet.web.render(translated_url, mode="text")
            prompt = self._review_prompt(source_text, translated_text, source_lang, target_lang)
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(self._normalize_verdict(raw), sort_keys=True)

        agreed_raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            principle=(
                "status must be exactly the same. "
                "issues may differ in wording only if they refer to the same "
                "underlying translation problem; the set of distinct issues "
                "identified must be substantively the same."
            ),
        )
        agreed = json.loads(agreed_raw)

        review_record = {
            "task_id": task_id,
            "translated_url": translated_url,
            "status": agreed["status"],
            "issues": agreed["issues"],
            "revision_number": task["revision_count"],
        }
        self.reviews[f"{task_id}:{task['revision_count']}"] = json.dumps(review_record)

        task["status"] = agreed["status"]
        if agreed["status"] != "accurate":
            task["revision_count"] += 1
        self.tasks[task_id] = json.dumps(task)

    @gl.public.view
    def get_review(self, task_id: str, revision_number: int) -> dict:
        key = f"{task_id}:{revision_number}"
        assert key in self.reviews, "no such review"
        return json.loads(self.reviews[key])

    def _get_reputation(self, address: str) -> dict:
        if address in self.reputation:
            return json.loads(self.reputation[address])
        return {"upheld": 0, "overturned": 0}

    @gl.public.view
    def get_reputation(self, address: str) -> dict:
        return self._get_reputation(address)

    @gl.public.write
    def contest_status(self, task_id: str, contester_argument: str) -> None:
        assert task_id in self.tasks, "no such task"
        task = json.loads(self.tasks[task_id])
        assert task["status"] in ("minor_issues", "inaccurate"), "nothing to contest"
        current_revision = task["revision_count"]
        review_key = f"{task_id}:{current_revision - 1}"
        assert review_key in self.reviews, "no review to contest"
        assert review_key not in self.disputes, "this review has already been contested"

        prior = json.loads(self.reviews[review_key])

        source_url = task["source_url"]
        source_lang = task["source_lang"]
        target_lang = task["target_lang"]
        translated_url = prior["translated_url"]

        extra = (
            f"A prior review reached status '{prior['status']}' citing issues: "
            f"{prior['issues']}. The translator disputes this and argues:\n"
            f"{contester_argument}\nRe-evaluate independently; you are not bound by the prior status."
        )

        def get_verdict() -> str:
            source_text = gl.nondet.web.render(source_url, mode="text")
            translated_text = gl.nondet.web.render(translated_url, mode="text")
            prompt = self._review_prompt(source_text, translated_text, source_lang, target_lang, extra)
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(self._normalize_verdict(raw), sort_keys=True)

        agreed_raw = gl.eq_principle.prompt_comparative(
            get_verdict,
            principle=(
                "status must be exactly the same. "
                "issues may differ in wording only if they refer to the same "
                "underlying translation problem; the set of distinct issues "
                "identified must be substantively the same."
            ),
        )
        agreed = json.loads(agreed_raw)
        overturned = STATUS_RANK[agreed["status"]] > STATUS_RANK[prior["status"]]

        contester = self._sender()
        rep = self._get_reputation(contester)
        if overturned:
            rep["overturned"] += 1
        else:
            rep["upheld"] += 1
        self.reputation[contester] = json.dumps(rep)

        task["status"] = agreed["status"]
        self.tasks[task_id] = json.dumps(task)

        self.disputes[review_key] = json.dumps({
            "task_id": task_id,
            "contester": contester,
            "argument": contester_argument,
            "prior_status": prior["status"],
            "new_status": agreed["status"],
            "overturned": overturned,
        })

    @gl.public.view
    def get_dispute(self, task_id: str, revision_number: int) -> dict:
        key = f"{task_id}:{revision_number}"
        assert key in self.disputes, "no dispute recorded"
        return json.loads(self.disputes[key])
