import type { RuleRetrievalEnvelope } from '../contracts/caseDecision'
import { CodeBlock, renderJsonLine } from './CodeBlock'

interface RuleRetrievalResultProps {
  envelope: RuleRetrievalEnvelope
  onAnnounce: (message: string) => void
}

/**
 * Rule mode returns rules, and this renders them as rules.
 *
 * There is deliberately no grouping by containing provision. Rule mode exists
 * to make the rule the unit of delivery, and grouping the results under their
 * parents here would put that unit back in front of the reader while the
 * payload no longer supports it -- the record carries the rule's own terms and
 * the identifiers needed to cite it, not the provision's body.
 *
 * The neighbour count is surfaced because a rule admitted as a `neighbour` is
 * in the set for a different reason than one that matched: a matched rule
 * depends on it. A reader comparing rule mode against policy mode needs to see
 * that some rows are dependencies rather than hits.
 */
export function RuleRetrievalResult(props: RuleRetrievalResultProps) {
  const count = props.envelope.rules.length
  const neighbours = props.envelope.rules.filter(
    (record) => record.match.admitted_as === 'neighbour',
  ).length

  return (
    <section
      className="panel policy-json-result"
      aria-labelledby="result-heading"
      data-testid="playground-rule-result"
    >
      <div className="panel__head policy-json-result__head">
        <div>
          <span className="eyebrow">Retrieval-only response</span>
          <h2 className="panel__title" id="result-heading" tabIndex={-1}>
            Filtered rule JSON
          </h2>
        </div>
        <span className="pill" data-testid="playground-rule-count">
          {count} {count === 1 ? 'rule' : 'rules'}
        </span>
        <p className="panel__subtitle">
          These are the exact selected published rules. No verdict, explanation, or receipt was
          generated.
          {neighbours > 0
            ? ` ${neighbours} of them ${
                neighbours === 1 ? 'was' : 'were'
              } admitted as a neighbour, because a matched rule depends on it.`
            : ''}
        </p>
      </div>
      <div className="panel__body">
        <CodeBlock
          text={JSON.stringify(props.envelope, null, 2)}
          language="JSON"
          what="the filtered rule JSON"
          downloadName="filtered-rules.json"
          testId="playground-rule-json"
          onAnnounce={props.onAnnounce}
          renderLine={renderJsonLine}
          maxHeight={720}
        />
      </div>
    </section>
  )
}
