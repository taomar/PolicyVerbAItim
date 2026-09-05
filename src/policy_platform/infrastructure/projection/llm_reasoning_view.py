"""An analyzed compact policy view that is not on the serving path.

WHY A SECOND VIEW AND NOT A SMALLER PROJECTION

`grounding_projection_v1` is the served record. It is the shape a receipt seals,
the shape `/policies` returns, the shape a citation resolves through, and the
shape a reviewer inspects — so it carries everything needed to *retrace* a
decision: the span dictionary keyed by content digest, each span's source hash,
page, section and character offsets, the Search document id, the rule revision,
the derived `evaluation_mode`, the DMN mapping status. Every one of those is a
fact about provenance, and none of them is a fact a model reasoning about a case
can use.

They are also the bulk of the bytes. A rule's own sentence is stored once in
`spans` and pointed at by id; the model therefore has to *join* — follow
`evidence_refs` into `spans`, follow `fact_ref` into `facts` — to read the two
things it actually reasons from. The joins cost the model attention and cost the
transport the whole dictionary apparatus that makes them possible.

So this builds a second view over the *same* records for measurement. It is not
sent to a model: both the flattened view and a later trace-only reduction moved
the scenario gate's missing-fact boundary, so serving was restored to the
complete `grounding_projection_v1`. The analysis remains because it measures
where the bytes are and gives a future design a reproducible starting point.

  * **Nothing is mutated.** The input dicts are read and never written to.
  * **Nothing operative is dropped.** Every selected rule appears, and every
    rule's exact source sentence appears — verbatim, uncut, in the document's own
    language, exactly as `spans` holds it. Beside it go the semantics a judgement
    turns on: the policy's heading and effective dates, and per rule its id,
    type, modality, effect, applicability attributes, facts and their roles,
    required facts, scope, exceptions, advice, override/supersession/relation
    markers, any date that departs from the policy's, and a non-default
    ambiguity marker.
  * **Only trace-only fields are dropped.** The schema and projection labels
    repeated on every policy, the UUID identity of policy/document/clause/Search
    document, span source hashes, pages, sections and offsets, `rule_revision`,
    `evaluation_mode` and the DMN status. None of them is readable evidence about
    what a rule requires.

WHAT IT DELIBERATELY DOES NOT DO

It does not measure anything, and it does not decide what is retained. The
retention budget and the one-gather oversize refusal are measured on
`grounding_projection_v1` exactly as they were, so a cheaper encoding can never
admit a policy the previous encoding would have refused. Making the model view
the budget would have been the quiet defect: the retained set would silently
widen, and every receipt's `retained`/`discarded` split would change with a
transport decision.

Nothing here names a domain, a corpus or a project. It reads only keys the
projection schema declares.
"""
from __future__ import annotations

#: Names and versions this transport, so a prompt can pin the shape it was
#: written against and a reader can tell it apart from the served record. It is
#: `v2` because it is the second view of one set of records, not a second
#: version of `grounding_projection_v1` — that one is untouched.
REASONING_VIEW = "llm_reasoning_v2"

#: The ambiguity value that says nothing was flagged. Emitted only when a rule
#: departs from it, because a marker present on every rule is not a marker.
_AMBIGUITY_DEFAULT = "none"

#: Rule keys copied straight through when present and non-empty. Each is
#: operative: a carve-out, a piece of non-blocking guidance, a scope that
#: narrows, the ids a rule supersedes or is read together with, the drafter's
#: tags. Order is the order the projection wrote them.
_PASSTHROUGH_RULE_KEYS = (
    "scope",
    "exceptions",
    "advice",
    "supersedes_rule_ids",
    "related_rule_ids",
    "tags",
)


def _text_for_ref(spans: dict, ref: object) -> str:
    """The verbatim sentence one evidence reference carries, or empty.

    A span records the clause it belongs to whether or not the passage itself
    was stored, so an entry without `text` is a supporting reference and carries
    no sentence. Read, never rewritten.
    """

    entry = spans.get(str(ref)) if isinstance(spans, dict) else None
    if not isinstance(entry, dict):
        return ""
    text = entry.get("text")
    return text if isinstance(text, str) else ""


def _rule_source(rule: dict, spans: dict) -> str:
    """The rule's own sentence, flattened out of the span dictionary.

    `project_rule` attaches the rule's quoted sentence to its *first* evidence
    reference and records the rest by clause identity alone, so the first
    reference that carries text is the sentence. Scanning rather than indexing
    `[0]` costs nothing and survives a rule whose leading reference was recorded
    without a passage.
    """

    for ref in rule.get("evidence_refs") or []:
        text = _text_for_ref(spans, ref)
        if text:
            return text
    return ""


def _fact_entries(rule: dict, facts: dict) -> list[dict]:
    """The rule's facts, resolved through the shared dictionary in place.

    The dictionary exists so a phrase used by twenty rules is stored once. That
    is the right shape for a record and the wrong one for a reader: the model
    would have to hold the dictionary and follow an id per fact per rule. Here
    each rule carries the fact it uses, with the verbatim `source_phrase` the
    dictionary holds and the roles the *rule* assigns it.
    """

    out: list[dict] = []
    for reference in rule.get("facts") or []:
        if not isinstance(reference, dict):
            continue
        entry = facts.get(str(reference.get("ref"))) if isinstance(facts, dict) else None
        if not isinstance(entry, dict):
            continue
        fact: dict = {"name": entry.get("name"), "phrase": entry.get("source_phrase")}
        if entry.get("data_type") is not None:
            fact["data_type"] = entry["data_type"]
        roles = list(reference.get("roles") or [])
        if roles:
            fact["roles"] = roles
        out.append(fact)
    return out


def _attribute_entries(attributes: object, facts: dict) -> list[dict]:
    """One side of a rule's attributes, with every phrase read out in full.

    An attribute either names a fact — in which case the projection points at
    the dictionary rather than copying the words — or carries its own verbatim
    text. Both arrive here as `text`, so the model reads a phrase where the
    record holds a pointer, and never has to know which of the two it was.

    `data_type` is carried only when the phrase named a kind. On the served
    record an explicit `null` is meaningful and is kept; in a transport an absent
    key says the same thing in fewer bytes, and the prompt says so.
    """

    out: list[dict] = []
    for attribute in attributes or []:
        if not isinstance(attribute, dict):
            continue
        entry: dict = {"attribute": attribute.get("attribute")}
        if "fact_ref" in attribute:
            resolved = facts.get(str(attribute["fact_ref"])) if isinstance(facts, dict) else None
            entry["text"] = (resolved or {}).get("source_phrase")
        else:
            entry["text"] = attribute.get("text")
        if attribute.get("data_type") is not None:
            entry["data_type"] = attribute["data_type"]
        out.append(entry)
    return out


def _rule_view(rule: dict, *, spans: dict, facts: dict) -> dict:
    """One rule as the model reads it: its sentence, then what it requires."""

    view: dict = {"rule_id": rule.get("rule_id")}

    source = _rule_source(rule, spans)
    if source:
        view["source"] = source

    if rule.get("rule_type") is not None:
        view["rule_type"] = rule["rule_type"]
    if rule.get("modality"):
        view["modality"] = rule["modality"]
    if rule.get("effect") is not None:
        view["effect"] = rule["effect"]

    applies = _attribute_entries((rule.get("attributes") or {}).get("applies"), facts)
    outcome = _attribute_entries((rule.get("attributes") or {}).get("outcome"), facts)
    if applies:
        view["applies"] = applies
    if outcome:
        view["outcome"] = outcome

    fact_entries = _fact_entries(rule, facts)
    if fact_entries:
        view["facts"] = fact_entries

    # Emitted even when empty, because `[]` here is the load-bearing statement
    # that the rule's test is words rather than named quantities — the same
    # distinction the projection keeps it for.
    view["required_facts"] = list(rule.get("required_facts") or [])

    for key in _PASSTHROUGH_RULE_KEYS:
        value = rule.get(key)
        if value:
            view[key] = value

    if rule.get("is_explicit_override"):
        view["is_explicit_override"] = True

    # Present on the record only when the rule departs from the policy's own
    # dates, and carried here on exactly the same terms.
    if "effective_from" in rule:
        view["effective_from"] = rule["effective_from"]
    if "effective_to" in rule:
        view["effective_to"] = rule["effective_to"]

    ambiguity = rule.get("ambiguity_status")
    if ambiguity is not None and str(ambiguity) != _AMBIGUITY_DEFAULT:
        view["ambiguity"] = ambiguity

    return view


def _policy_view(entry: dict) -> dict:
    """One retained policy, flattened around its rules.

    `entry` is what the retrieval layer already pairs for the gather:
    ``{"policy": <identity>, "record": <grounding_projection_v1>}``. The
    identity's `provision_id` is a UUID and is dropped; its `heading_path` is the
    only prose the envelope carries and becomes the policy's readable name. The
    `provision_key` stays, because it is the platform-wide identity of a policy
    and is not a UUID — two policies can share a heading.
    """

    identity = entry.get("policy") or {}
    record = entry.get("record") or {}
    envelope = record.get("envelope") or {}
    spans = record.get("spans") or {}
    facts = record.get("facts") or {}

    heading_path = identity.get("heading_path")
    if not heading_path:
        heading_path = envelope.get("heading_path") or []

    view: dict = {
        "policy": " > ".join(str(part) for part in heading_path),
        "provision_key": identity.get("provision_key") or envelope.get("provision_key"),
    }
    if envelope.get("effective_from") is not None:
        view["effective_from"] = envelope["effective_from"]
    if envelope.get("effective_to") is not None:
        view["effective_to"] = envelope["effective_to"]

    view["rules"] = [
        _rule_view(rule, spans=spans, facts=facts)
        for rule in record.get("rules") or []
        if isinstance(rule, dict)
    ]
    return view


def build_reasoning_view(policies_view: list[dict]) -> dict:
    """The retained policies as `llm_reasoning_v2`, built from the served records.

    ``policies_view`` is the list the gather already assembles — one entry per
    retained policy, its identity paired with its `grounding_projection_v1`
    record. Nothing in it is modified; every value carried across is either
    copied or read.

    The `view` marker is the one piece of self-description that survives, in
    place of the `projection` and `representation` labels the record repeats on
    every policy: a prompt written against this shape can name the shape it was
    written against, once.
    """

    return {
        "view": REASONING_VIEW,
        "policies": [
            _policy_view(entry) for entry in policies_view if isinstance(entry, dict)
        ],
    }
