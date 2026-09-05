import { describe, expect, it } from 'vitest'
import {
  buildPolicyRequestBody,
  buildRequestBody,
  casePath,
  hostFromBase,
  joinUrl,
  lightCasePath,
  policiesPath,
  requestBodyJson,
} from './requestBody'
import { MAX_ADDITIONAL_INSTRUCTIONS_CHARS } from '../contracts/caseDecision'

const base = {
  scenario: 'A supplier in a sanctioned jurisdiction asks about 90-day terms.',
  reasoningEffort: 'medium' as const,
  callingSystemIdentity: 'playground-demo',
  // The default position of the retrieval control, stated once here so every
  // test below reads as "and the default mode", and the rule-mode tests read
  // as the deliberate departure they are.
  ruleRetrieval: false,
}

describe('buildRequestBody — what actually goes on the wire', () => {
  it('omits additional_instructions entirely when the field is empty', () => {
    const body = buildRequestBody({ ...base, additionalInstructions: '' })
    expect(Object.keys(body)).toEqual(['scenario', 'reasoning_effort', 'calling_system_identity'])
    expect('additional_instructions' in body).toBe(false)
    // Not `""` and not `null`: an empty string is a value the receipt would
    // echo back, an absent key is an absence the receipt can report as one.
    expect(JSON.stringify(body)).not.toContain('additional_instructions')
  })

  it('omits it for whitespace-only guidance too', () => {
    const body = buildRequestBody({ ...base, additionalInstructions: '   \n\t  ' })
    expect('additional_instructions' in body).toBe(false)
  })

  it('sends present guidance trimmed, so what is previewed is what is sent', () => {
    const body = buildRequestBody({
      ...base,
      additionalInstructions: '  Explain the approval path first.  ',
    })
    expect(body.additional_instructions).toBe('Explain the approval path first.')
  })

  it('never carries correlation or idempotency, which are headers', () => {
    const parsed = JSON.parse(requestBodyJson({ ...base, additionalInstructions: 'x' })) as Record<
      string,
      unknown
    >
    expect(parsed).not.toHaveProperty('correlation_id')
    expect(parsed).not.toHaveProperty('idempotency_key')
    expect(parsed).not.toHaveProperty('Idempotency-Key')
  })

  it('keeps the wire key order stable', () => {
    const json = requestBodyJson({ ...base, additionalInstructions: 'guide' })
    const order = ['scenario', 'reasoning_effort', 'calling_system_identity', 'additional_instructions']
    const indices = order.map((key) => json.indexOf(`"${key}"`))
    expect(indices).toEqual([...indices].sort((a, b) => a - b))
    expect(indices.every((i) => i >= 0)).toBe(true)
  })

  it('trims the scenario as well', () => {
    expect(buildRequestBody({ ...base, scenario: '  hello  ', additionalInstructions: '' }).scenario).toBe(
      'hello',
    )
  })

  it('accepts guidance right up to the documented ceiling', () => {
    const guidance = 'x'.repeat(MAX_ADDITIONAL_INSTRUCTIONS_CHARS)
    const body = buildRequestBody({ ...base, additionalInstructions: guidance })
    expect(body.additional_instructions).toHaveLength(MAX_ADDITIONAL_INSTRUCTIONS_CHARS)
  })

  it('builds the light request from the scenario alone', () => {
    const body = buildPolicyRequestBody({
      ...base,
      additionalInstructions: 'This must not reach retrieval.',
    })
    expect(body).toEqual({ scenario: base.scenario })
    expect(body).not.toHaveProperty('reasoning_effort')
    expect(body).not.toHaveProperty('calling_system_identity')
    expect(body).not.toHaveProperty('additional_instructions')
  })
})

describe('rule_retrieval — a key that only exists when it is true', () => {
  it('omits the key entirely in the default mode', () => {
    // Not `false`. The server's idempotency preimage omits it when false, so a
    // body carrying `"rule_retrieval": false` would put a key on the wire that
    // the hash this page previews beside it does not contain.
    const body = buildRequestBody({ ...base, additionalInstructions: '' })
    expect('rule_retrieval' in body).toBe(false)
    expect(JSON.stringify(body)).not.toContain('rule_retrieval')
  })

  it('writes it as true when the caller asked for rule retrieval', () => {
    const body = buildRequestBody({
      ...base,
      additionalInstructions: '',
      ruleRetrieval: true,
    })
    expect(body.rule_retrieval).toBe(true)
  })

  it('applies the same rule to the light retrieval body', () => {
    const off = buildPolicyRequestBody({ ...base, additionalInstructions: '' })
    const on = buildPolicyRequestBody({
      ...base,
      additionalInstructions: '',
      ruleRetrieval: true,
    })

    expect(off).toEqual({ scenario: base.scenario })
    expect(on).toEqual({ scenario: base.scenario, rule_retrieval: true })
  })

  it('keeps it last in wire order, after every field that predates it', () => {
    const json = requestBodyJson({
      ...base,
      additionalInstructions: 'guide',
      ruleRetrieval: true,
    })
    const order = [
      'scenario',
      'reasoning_effort',
      'calling_system_identity',
      'additional_instructions',
      'rule_retrieval',
    ]
    const indices = order.map((key) => json.indexOf(`"${key}"`))
    expect(indices.every((index) => index >= 0)).toBe(true)
    expect(indices).toEqual([...indices].sort((a, b) => a - b))
  })
})

describe('url construction', () => {
  it('routes on the project key, never on a UUID or a name', () => {
    expect(casePath('demo-project')).toBe('/api/policy-decisions/demo-project/case')
    expect(lightCasePath('demo-project')).toBe('/api/policy-decisions/demo-project/case/light')
    expect(policiesPath('demo-project')).toBe('/api/policy-decisions/demo-project/policies')
  })

  it('escapes a key so a stray slash cannot rewrite the path', () => {
    expect(casePath('a/b')).toBe('/api/policy-decisions/a%2Fb/case')
  })

  it('joins without doubling a slash and without losing a base path prefix', () => {
    expect(joinUrl('https://host/', '/api/x')).toBe('https://host/api/x')
    expect(joinUrl('https://host/gateway', '/api/x')).toBe('https://host/gateway/api/x')
  })

  it('shows an unparsable base as written rather than withholding the preview', () => {
    expect(hostFromBase('not a url')).toBe('not a url')
    expect(hostFromBase('https://policy.example.com:8443/x')).toBe('policy.example.com:8443')
  })
})
