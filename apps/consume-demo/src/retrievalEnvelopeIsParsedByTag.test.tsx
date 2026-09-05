// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import {
  POLICY_RETRIEVAL_SCHEMA_VERSION,
  RULE_RETRIEVAL_SCHEMA_VERSION,
  classifyRetrieval,
  type PolicyRetrievalEnvelope,
  type RetrievedRuleRecord,
  type RuleRetrievalEnvelope,
} from './contracts/caseDecision'
import { mapUnsupportedRetrievalError } from './lib/errors'
import { PolicyRetrievalResult } from './components/PolicyRetrievalResult'
import { RuleRetrievalResult } from './components/RuleRetrievalResult'

/**
 * A retrieval response is read by its schema tag, and refused when it is not
 * one this build knows and well formed.
 *
 * The failure these tests exist to prevent is not a crash. It is the silent
 * one: a response carrying rules, read by a build that only knows policies,
 * reporting "0 policies were retrieved" -- a sentence indistinguishable from a
 * genuine "nothing bears on this question". A wrong answer that looks like a
 * right one is worse than an error, because nothing signals it happened.
 *
 * The groups below are deliberate. Refusals alone would be satisfied by a
 * parser that refused everything, so each is paired with a control. The pair
 * that matters most is "own collection empty" against "own collection missing":
 * an empty answer is a real answer and must render, a missing one is a
 * malformed response and must not.
 */

afterEach(cleanup)

const SENTINEL = 'EMPLOYEES-MUST-NOT-DISCLOSE-CONFIDENTIAL-SALARY-BANDS'

function ruleRecord(id = 'R-1', admittedAs = 'matched'): RetrievedRuleRecord {
  return {
    rule_id: id,
    source: { provision_key: 'PK-1', heading_path: ['Part 1'] },
    match: { best_rank: 1, admitted_as: admittedAs },
    rule: { text: 'A rule that says something.' },
  }
}

function policyRecord(key = 'PK-1') {
  return {
    policy: { provision_key: key, heading_path: ['Part 1'] },
    match: { best_rank: 1 },
    payload: { text: 'A provision that says something.' },
  }
}

/** The envelope members both modes share, so a case can vary only what it tests. */
function common() {
  return {
    correlation_id: 'c-1',
    policy_set: { key: 'demo-project', name: 'Demo' },
    query: { scenario: 'a scenario', scenario_hash: 'h' },
    retrieval: { status: 'narrowed' },
    size: { combined_chars: 10 },
    language: {},
    token_usage: { calls: 0 },
    latency_ms: 5,
  }
}

function policyEnvelope(overrides: Record<string, unknown> = {}) {
  return {
    ...common(),
    schema_version: POLICY_RETRIEVAL_SCHEMA_VERSION,
    policies: [policyRecord()],
    ...overrides,
  }
}

function ruleEnvelope(overrides: Record<string, unknown> = {}) {
  return {
    ...common(),
    schema_version: RULE_RETRIEVAL_SCHEMA_VERSION,
    rules: [ruleRecord()],
    ...overrides,
  }
}

// ── A. the tag is refused when it is not one of ours ──────────────────

describe('an unknown or missing schema version is refused', () => {
  it('refuses a version this build has never heard of', () => {
    expect(classifyRetrieval(ruleEnvelope({ schema_version: 'rule_retrieval_v9' }))).toBe(
      'unrecognised',
    )
  })

  it('refuses a body carrying no schema version at all', () => {
    expect(classifyRetrieval({})).toBe('unrecognised')
  })

  it('refuses a body that is not an object, and one that carries no tag to recognise', () => {
    // A tagless array is `unrecognised`, not `invalid`: `invalid` would claim we
    // recognised a version and found its records wrong, which is a different
    // and false statement about a body carrying no version at all.
    expect(classifyRetrieval(null)).toBe('unrecognised')
    expect(classifyRetrieval('nope')).toBe('unrecognised')
    expect(classifyRetrieval([])).toBe('unrecognised')
    expect(classifyRetrieval({ schema_version: 7, policies: [] })).toBe('unrecognised')
  })
})

// ── B. the two modes never mix, checked both ways round ───────────────

describe('a response carrying both modes is refused rather than narrowed', () => {
  it('refuses a rule response that also carries policy records', () => {
    expect(classifyRetrieval(ruleEnvelope({ policies: [policyRecord()] }))).toBe('mixed')
  })

  it('refuses a policy response that also carries rule records', () => {
    expect(classifyRetrieval(policyEnvelope({ rules: [ruleRecord()] }))).toBe('mixed')
  })
})

// ── C. the answer must be present; empty is an answer, missing is not ─

describe('the collection the tag names must be present and a list', () => {
  it('refuses a policy response whose policies are missing entirely', () => {
    const { policies: _dropped, ...withoutOwn } = policyEnvelope()
    expect(classifyRetrieval(withoutOwn)).toBe('invalid')
  })

  it('refuses a rule response whose rules are missing entirely', () => {
    const { rules: _dropped, ...withoutOwn } = ruleEnvelope()
    expect(classifyRetrieval(withoutOwn)).toBe('invalid')
  })

  it('refuses an own collection that is present but not a list', () => {
    expect(classifyRetrieval(policyEnvelope({ policies: 'oops' }))).toBe('invalid')
    expect(classifyRetrieval(ruleEnvelope({ rules: null }))).toBe('invalid')
  })

  it('accepts an empty policy list, because finding nothing is a real answer', () => {
    expect(classifyRetrieval(policyEnvelope({ policies: [] }))).toBe('policy')
  })

  it('accepts an empty rule list, for the same reason', () => {
    expect(classifyRetrieval(ruleEnvelope({ rules: [] }))).toBe('rule')
  })
})

// ── D. controls: a parser that refused everything would pass A-C ──────

describe('well formed responses are accepted', () => {
  it('accepts a populated policy response', () => {
    expect(classifyRetrieval(policyEnvelope())).toBe('policy')
  })

  it('accepts a populated rule response', () => {
    expect(classifyRetrieval(ruleEnvelope())).toBe('rule')
  })
})

// ── E. the other mode's field may be absent or empty, never read ──────

describe('the opposite collection is tolerated in either wire shape', () => {
  it('accepts a rule response with no policies property at all', () => {
    const envelope = ruleEnvelope()
    expect('policies' in envelope).toBe(false)
    expect(classifyRetrieval(envelope)).toBe('rule')
  })

  it('accepts a rule response carrying an empty policies list, and still reads it as rules', () => {
    // A rolling deployment or a pinned older API can still send the empty form.
    // Reading `policies` here would report "0 policies retrieved" for a response
    // that returned rules -- the silent misreport this whole guard exists for.
    expect(classifyRetrieval(ruleEnvelope({ policies: [] }))).toBe('rule')
  })
})

// ── the rendered surfaces answer in their own unit ────────────────────

describe('each mode renders in the unit it answered with', () => {
  it('renders rules, and never reports a policy count, for a rule response', () => {
    const envelope = ruleEnvelope({
      rules: [ruleRecord('R-1'), ruleRecord('R-2', 'neighbour')],
    }) as unknown as RuleRetrievalEnvelope
    render(<RuleRetrievalResult envelope={envelope} onAnnounce={() => {}} />)

    expect(screen.getByTestId('playground-rule-count').textContent).toContain('2 rules')
    expect(screen.getByTestId('playground-rule-result').textContent).toContain('neighbour')
    expect(screen.queryByTestId('playground-policy-count')).toBeNull()
    expect(document.body.textContent).not.toContain('0 policies')
  })

  it('still renders an empty policy response as the genuine negative it is', () => {
    const envelope = policyEnvelope({ policies: [] }) as unknown as PolicyRetrievalEnvelope
    render(<PolicyRetrievalResult envelope={envelope} onAnnounce={() => {}} />)
    expect(screen.getByTestId('playground-policy-count').textContent).toContain('0 policies')
  })
})

// ── leakage: a refusal must not carry the corpus with it ──────────────

describe('a refused response does not leak what it contained', () => {
  it('reports the shape of an unreadable response without quoting any of it', () => {
    const leaky = ruleEnvelope({
      rules: [
        {
          rule_id: 'R-1',
          source: { provision_key: SENTINEL, heading_path: [SENTINEL] },
          match: { admitted_as: 'matched' },
          rule: { text: SENTINEL },
        },
      ],
      policies: [{ policy: { provision_key: SENTINEL }, match: {}, payload: { text: SENTINEL } }],
    })

    const error = mapUnsupportedRetrievalError({
      kind: 'mixed',
      status: 200,
      correlationId: 'c-1',
      body: leaky,
    })

    // The whole error is copyable from the UI, so the whole error is checked --
    // asserting only that `detail` "looks structural" would pass even if the
    // body had been attached somewhere else on it.
    expect(JSON.stringify(error)).not.toContain(SENTINEL)
    expect(error.detail).toEqual({
      schema_version: RULE_RETRIEVAL_SCHEMA_VERSION,
      policies: 'array(1)',
      rules: 'array(1)',
      keys: Object.keys(leaky).length,
    })
  })

  it('describes a malformed collection without reporting it as an empty one', () => {
    const error = mapUnsupportedRetrievalError({
      kind: 'invalid',
      status: 200,
      body: policyEnvelope({ policies: undefined }),
    })
    expect(error.detail).toMatchObject({ policies: 'absent' })
    expect(error.body).toContain('missing or malformed')
    expect(error.body).not.toContain('nothing')
  })

  it('offers no retry, because retrying returns the same unreadable answer', () => {
    for (const kind of ['unrecognised', 'mixed', 'invalid'] as const) {
      const error = mapUnsupportedRetrievalError({ kind, status: 200, body: {} })
      expect(error.recovery).toBe('none')
      expect(error.code).toBe('unsupported_schema_version')
    }
  })
})
