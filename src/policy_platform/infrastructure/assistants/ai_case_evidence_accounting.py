"""Whether a reply accounted for every unit of evidence it was handed.

THE DEFECT

An answer can rest on one of the two provisions it was given and read as though
it had weighed both. Retrieval's verdict was recorded; the answer's was not. A
receipt could therefore show a policy carried into the evaluation, contributing
nothing, and look exactly like one where it had been read and found not to apply.

WHY THE MODEL DECLARES IT AND THE SERVER ONLY CHECKS

The server can see which citations exist, so it can say *cited* or *uncited*. It
cannot say **relevant**: that is a claim about whether the evidence bore on the
question, and only the reader of the question and the record can make it. A
server-derived label therefore documents the gap and never closes it — the same
reply stays successful with the unit merely marked unused.

So the claim is the model's, and this module checks it. The division is the point:
the model says what it did, the server refuses to call the result an answer unless
what it did covers everything it was given.

WHAT IS NOT REQUIRED

Not that every unit be cited. Retrieval keeps more than any one answer needs, and
demanding citations for all of it would buy completeness with precision — the
degenerate repair. Setting evidence aside is legitimate; setting it aside
*silently* is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from policy_platform.infrastructure.assistants.ai_case_plan import (
    DISPOSITION_IRRELEVANT,
    DISPOSITION_USED,
    CasePlan,
    EvidenceDisposition,
)

#: Why an answered status could not stand. Closed, and named for the reader of a
#: log rather than for this module: each value states what was wrong with the
#: accounting, not which branch rejected it.
ACCOUNTING_UNDECLARED: Final[str] = "evidence_dispositions_absent"
ACCOUNTING_INCOMPLETE: Final[str] = "evidence_unit_undispositioned"
ACCOUNTING_UNRECOGNISED: Final[str] = "evidence_disposition_unrecognised"
ACCOUNTING_UNOWNED: Final[str] = "evidence_used_without_owned_citation"
ACCOUNTING_UNREASONED: Final[str] = "evidence_set_aside_without_reason"


@dataclass(frozen=True, slots=True)
class EvidenceAccounting:
    """The verdict on one reply's accounting, and why."""

    complete: bool
    #: Closed tokens, in a stable order, naming every way the accounting failed.
    #: Plural because one reply can fail in several ways at once and a reader who
    #: fixed only the first would be told the same story again.
    failures: tuple[str, ...] = ()
    #: The evidence units the reply did not account for, as this module resolved
    #: them. Identities only.
    unaccounted_keys: tuple[str, ...] = ()

    @property
    def blocks_answer(self) -> bool:
        return not self.complete


def _owned(claim: EvidenceDisposition, available_rule_ids: frozenset[str]) -> bool:
    """Whether a `used` claim names at least one citation that actually exists.

    Ownership is checked against the closed rule set the reply was given, not
    against the citations it happened to list elsewhere: a claim that owns a rule
    id nobody handed over is not evidence of use, it is a second fabrication.
    """

    return any(rule_id in available_rule_ids for rule_id in claim.rule_ids)


def account_for_evidence(
    plan: CasePlan,
    *,
    evidence_keys: frozenset[str],
    available_rule_ids: frozenset[str],
) -> EvidenceAccounting:
    """Check a reply's account of the evidence against the evidence it was given.

    Four things are checked, and each is a different way an answer can rest on
    less than it was handed:

      * **Totality.** Every unit handed over is named. A unit the reply never
        mentions is one it made no claim about.
      * **Recognition.** Every disposition is one of the closed tokens. An
        invented token is a claim this platform cannot read, which is the same
        position as no claim at all.
      * **Ownership.** A unit said to be `used` names at least one citation from
        the closed rule set. "I relied on this" without saying through what is not
        an account of use.
      * **Disclosure.** A unit set aside says why. Presence, never content — the
        reason itself is prose and is never read here.

    Units named by the reply that were never handed over are ignored rather than
    treated as failures: they cannot make the account of the real evidence any
    less complete, and the closed rule set already refuses fabricated citations.

    When no evidence was handed over at all there is nothing to account for, and
    an empty declaration is complete rather than absent. A reply is not asked to
    account for evidence that does not exist.
    """

    if not evidence_keys:
        return EvidenceAccounting(complete=True)

    if not plan.evidence_dispositions:
        return EvidenceAccounting(
            complete=False,
            failures=(ACCOUNTING_UNDECLARED,),
            unaccounted_keys=tuple(sorted(evidence_keys)),
        )

    by_key: dict[str, EvidenceDisposition] = {}
    for claim in plan.evidence_dispositions:
        # First claim wins. A reply that dispositions one unit twice has not made
        # two decisions about it; taking the last would let a later entry quietly
        # overturn an earlier one.
        by_key.setdefault(claim.key, claim)

    failures: list[str] = []
    unaccounted: list[str] = []

    for key in sorted(evidence_keys):
        claim = by_key.get(key)
        if claim is None:
            unaccounted.append(key)
            if ACCOUNTING_INCOMPLETE not in failures:
                failures.append(ACCOUNTING_INCOMPLETE)
            continue
        if not claim.is_recognised:
            unaccounted.append(key)
            if ACCOUNTING_UNRECOGNISED not in failures:
                failures.append(ACCOUNTING_UNRECOGNISED)
            continue
        if claim.disposition == DISPOSITION_USED and not _owned(claim, available_rule_ids):
            unaccounted.append(key)
            if ACCOUNTING_UNOWNED not in failures:
                failures.append(ACCOUNTING_UNOWNED)
            continue
        if claim.disposition == DISPOSITION_IRRELEVANT and not claim.states_reason:
            unaccounted.append(key)
            if ACCOUNTING_UNREASONED not in failures:
                failures.append(ACCOUNTING_UNREASONED)

    return EvidenceAccounting(
        complete=not failures,
        failures=tuple(failures),
        unaccounted_keys=tuple(unaccounted),
    )
