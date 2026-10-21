import type { Analysis } from '../api'
import { names } from '../api'
import { Badge } from './common'

export function SentenceBreakdown({ analysis }: { analysis: Analysis }) {
  if (!analysis.sentences.length) return null

  return (
    <div className="sentence-breakdown">
      <h3>Sentence-by-sentence analysis</h3>
      <p className="sentence-intro">
        Sentences stay in reading order. Each row shows an opinion about a specific feature;
        separate opinions within a sentence keep their own labels.
      </p>
      {analysis.sentences.map((sentence, index) => {
        const opinions = analysis.aspects
          .flatMap((aspect) =>
            aspect.evidence
              .filter((evidence) => evidence.sentence_id === sentence.id)
              .map((evidence) => ({ category: aspect.category, evidence })),
          )
          .sort((a, b) => a.evidence.start - b.evidence.start)
        const general = analysis.general_opinion?.evidence.filter(
          (evidence) => evidence.sentence_id === sentence.id,
        )
        return (
          <article className="sentence-card" key={sentence.id}>
            <h4>Sentence {index + 1}</h4>
            <blockquote className="original-sentence">{sentence.text}</blockquote>
            <div className="sentence-opinions">
              {opinions.map(({ category, evidence }, opinionIndex) => (
                <div className="sentence-opinion" key={`${category}-${opinionIndex}`}>
                  <div className="opinion-label">
                    <strong>{names[category]}</strong>
                    <Badge state={evidence.sentiment} />
                  </div>
                  {evidence.text !== sentence.text && (
                    <blockquote className="opinion-context">{evidence.text}</blockquote>
                  )}
                  {analysis.inference_steps?.some(
                    (step) =>
                      step.sentence_id === sentence.id &&
                      step.category === category &&
                      step.start === evidence.start &&
                      step.end === evidence.end &&
                      step.score < 0.6,
                  ) && (
                    <p className="uncertain-decision">Uncertain prediction — check this opinion.</p>
                  )}
                </div>
              ))}
              {general?.map((evidence, generalIndex) => (
                <div className="sentence-opinion" key={`general-${generalIndex}`}>
                  <div className="opinion-label">
                    <strong>General phone opinion</strong>
                    <Badge state={evidence.sentiment} />
                  </div>
                </div>
              ))}
              {!opinions.length && !general?.length && (
                <p className="sentence-unmatched">No supported phone feature identified here.</p>
              )}
            </div>
          </article>
        )
      })}
    </div>
  )
}
