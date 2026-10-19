import { useEffect, useState } from 'react'
import { ChevronDown, ChevronLeft, ChevronRight, Loader2, Search, Smartphone } from 'lucide-react'
import { names, number, query } from '../api'
import type { FilterValues, Review, ReviewPage } from '../api'
import { useRemote } from '../hooks/useRemote'
import { Badge, Empty } from './common'

function ReviewsView({
  base,
  filters,
  revision,
  compact = false,
}: {
  base: string
  filters: FilterValues
  revision: number
  compact?: boolean
}) {
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(null)
  useEffect(() => {
    setPage(1)
    setExpanded(null)
  }, [base, query(filters)])
  const result = useRemote<ReviewPage>(
    `${base}/reviews?${query(filters)}&page=${page}&page_size=${compact ? 3 : 12}`,
    revision,
  )
  if (result.error)
    return (
      <div className="inline-error" role="alert">
        {result.error}
      </div>
    )
  if (!result.data)
    return (
      <div className="loading-line">
        <Loader2 className="spin" size={17} />
        Loading reviews…
      </div>
    )
  if (!result.data.items.length)
    return (
      <Empty title="No reviews match these filters" icon={<Search size={25} />}>
        Try a different aspect, sentiment, or search phrase.
      </Empty>
    )
  return (
    <>
      <div className="review-list">
        {result.data.items.map((review) => (
          <ReviewCard
            key={review.id}
            review={review}
            expanded={expanded === review.id}
            onToggle={() => setExpanded(expanded === review.id ? null : review.id)}
          />
        ))}
      </div>
      {!compact && (
        <div className="pagination">
          <span>
            {number((page - 1) * 12 + 1)}–{number(Math.min(page * 12, result.data.total))} of{' '}
            {number(result.data.total)} reviews
          </span>
          <div>
            <button
              aria-label="Previous page"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={16} />
            </button>
            <span>Page {page}</span>
            <button
              aria-label="Next page"
              disabled={page * 12 >= result.data.total}
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </>
  )
}

function ReviewCard({
  review,
  expanded,
  onToggle,
}: {
  review: Review
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <article className={`review-card ${expanded ? 'expanded' : ''}`}>
      <button className="review-main" onClick={onToggle} aria-expanded={expanded}>
        <span className="phone-icon">
          <Smartphone size={19} />
        </span>
        <div className="review-content">
          <div className="review-meta">
            <strong>{review.product_name}</strong>
            <span>{review.date || 'Date unavailable'}</span>
            {review.rating !== null && (
              <span className="rating">
                ★ {review.rating}
                <span> overall</span>
              </span>
            )}
          </div>
          <p className={expanded ? '' : 'line-clamp'}>{review.text}</p>
          <div className="review-aspects">
            {review.analysis?.aspects.map((aspect) => (
              <span key={aspect.category} className={`aspect-pill ${aspect.sentiment}`}>
                <i />
                {names[aspect.category]}
              </span>
            ))}
            {!review.analysis && <span className="muted">Awaiting analysis</span>}
            {review.analysis && !review.analysis.aspects.length && (
              <span className="muted">
                {review.analysis.supported
                  ? 'No explicit aspect detected'
                  : 'Language not supported'}
              </span>
            )}
          </div>
        </div>
        <ChevronDown size={17} className={expanded ? 'rotated' : ''} />
      </button>
      {expanded && review.analysis && (
        <div className="review-evidence">
          {review.analysis.aspects.map((aspect) => (
            <div className="evidence-row" key={aspect.category}>
              <div>
                <strong>{names[aspect.category]}</strong>
                <Badge state={aspect.sentiment} />
              </div>
              {aspect.evidence.map((evidence, index) => (
                <blockquote key={index}>{evidence.text}</blockquote>
              ))}
            </div>
          ))}
          <p className="evidence-caption">
            {review.analysis.model_id} · Supporting sentences from the original review. Lexicon
            scores are not confidence probabilities.
          </p>
        </div>
      )}
    </article>
  )
}

export default ReviewsView
