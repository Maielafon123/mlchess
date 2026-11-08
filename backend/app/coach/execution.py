"""Hard subprocess deadline around the allowlisted provider, with no SQL/secrets."""

from dataclasses import asdict
import json
import os
import subprocess
import sys

from backend.app.coach.grounding import AnalysisFacts, validate_explanation
from backend.app.coach.providers.base import CoachRequest
from backend.app.coach.providers.rules import RulesCoachProvider
from backend.app.coach.service import CoachJob, CoachService


def execute(provider, job: CoachJob, facts, *, timeout=8):
    if not 0 < timeout <= 8:
        raise ValueError("Provider timeout must be bounded")
    try:
        if type(provider) is not RulesCoachProvider:
            raise ValueError("Provider is not enabled for isolated execution")
        data = {
            "job_id": job.id,
            "request": asdict(job.request),
            "facts": {
                **asdict(facts),
                "verified_uci": sorted(facts.verified_uci),
                "verified_highlights": sorted(facts.verified_highlights),
                "claim_refs": sorted(facts.claim_refs),
            },
        }
        encoded = json.dumps(data).encode("utf-8")
        if len(encoded) > 32768:
            raise ValueError("Provider context exceeds its bound")
        allowed_env = {
            "PATH",
            "SYSTEMROOT",
            "SystemRoot",
            "WINDIR",
            "TEMP",
            "TMP",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "PYTHONDONTWRITEBYTECODE",
        }
        result = subprocess.run(
            [sys.executable, "-m", "backend.app.coach.execution", "--child"],
            input=encoded,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=True,
            env={key: value for key, value in os.environ.items() if key in allowed_env},
        )
        if len(result.stdout) > 32768:
            raise ValueError("Provider output exceeds its bound")
        checked = validate_explanation(
            json.loads(result.stdout)["explanation"], job.request, facts
        )
        return checked.explanation, checked.failure_code
    except Exception:
        fallback = validate_explanation(None, job.request, facts)
        return fallback.explanation, "PROVIDER_UNAVAILABLE"


def child():
    encoded = sys.stdin.buffer.read(32769)
    if len(encoded) > 32768:
        return 1
    data = json.loads(encoded)
    request = CoachRequest(**data["request"])
    raw_facts = data["facts"]
    for key in ("verified_uci", "verified_highlights", "claim_refs"):
        raw_facts[key] = frozenset(raw_facts[key])
    facts = AnalysisFacts(**raw_facts)
    service = CoachService(provider=RulesCoachProvider())
    job = CoachJob(id=data["job_id"], request=request, cache_key="isolated")
    service.jobs[job.id] = job
    done = service.run(job.id, facts)
    result = json.dumps({"explanation": done.explanation}).encode("utf-8")
    if len(result) > 32768:
        return 1
    sys.stdout.buffer.write(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(child() if sys.argv[1:] == ["--child"] else 1)
    except Exception:
        raise SystemExit(1) from None
