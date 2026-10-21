import { useState } from 'react'
import { CircleHelp, GitCompareArrows } from 'lucide-react'
import { phoneName, colors, dateRange, names, number, states } from '../api'
import type { Overview, Product } from '../api'
import { Empty } from '../components/common'
import { useRemote } from '../hooks/useRemote'

function CompareView({
  base,
  products,
  revision,
  modelId,
}: {
  base: string
  products: Product[]
  revision: number
  modelId: string
}) {
  const [selection, setSelection] = useState<{ base: string; ids: string[] } | null>(null)
  const selected =
    selection?.base === base ? selection.ids : [products[0]?.id || '', products[1]?.id || '', '']
  const chosen = selected.filter(Boolean)
  const url =
    chosen.length >= 2
      ? `${base}/compare?${chosen.map((id) => `products=${encodeURIComponent(id)}`).join('&')}&model=${modelId}`
      : null
  const result = useRemote<(Overview & { product_id: string })[]>(url, revision)
  return (
    <section className="panel compare-panel">
      <div className="panel-title">
        <div>
          <h2>Phones, side by side</h2>
          <p>Select two or three models. Values are net sentiment, from −100 to +100.</p>
        </div>
        <span className="subtle-chip">HISTORICAL REVIEWS</span>
      </div>
      <div className="compare-pickers">
        {[0, 1, 2].map((index) => (
          <label key={index}>
            <span>
              PHONE {index + 1}
              {index === 2 && ' · OPTIONAL'}
            </span>
            <select
              aria-label={`Comparison phone ${index + 1}`}
              value={selected[index] || ''}
              onChange={(event) => {
                const next = [...selected]
                next[index] = event.target.value
                setSelection({ base, ids: next })
              }}
            >
              <option value="">Select a phone</option>
              {products
                .filter(
                  (product) => product.id === selected[index] || !selected.includes(product.id),
                )
                .map((product) => (
                  <option value={product.id} key={product.id}>
                    {phoneName(product.name, product.brand)}
                  </option>
                ))}
            </select>
          </label>
        ))}
      </div>
      {result.error && (
        <div className="inline-error" role="alert">
          {result.error}
        </div>
      )}
      {!result.data || chosen.length < 2 ? (
        <Empty title="Choose models to compare" icon={<GitCompareArrows size={26} />}>
          At least two phone models with analysed reviews are needed.
        </Empty>
      ) : (
        <div className="comparison-scroll">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Aspect</th>
                {result.data.map((summary) => (
                  <th key={summary.product_id}>
                    <strong>
                      {phoneName(
                        products.find((product) => product.id === summary.product_id)?.name ||
                          'Phone',
                        products.find((product) => product.id === summary.product_id)?.brand,
                      )}
                    </strong>
                    <span>{number(summary.analysed)} analysed reviews</span>
                    <span>{dateRange(summary.date_from, summary.date_to)}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.keys(names).map((category) => (
                <tr key={category}>
                  <th>{names[category]}</th>
                  {result.data!.map((summary) => {
                    const aspect = summary.aspects.find((row) => row.category === category)!
                    return (
                      <td key={summary.product_id}>
                        <strong
                          className={
                            aspect.net_sentiment === null
                              ? ''
                              : aspect.net_sentiment >= 0
                                ? 'positive-text'
                                : 'negative-text'
                          }
                        >
                          {aspect.net_sentiment === null
                            ? '—'
                            : `${aspect.net_sentiment > 0 ? '+' : ''}${aspect.net_sentiment}`}
                        </strong>
                        <span>
                          {number(aspect.mentions)} mentions
                          {aspect.limited_evidence ? ' · limited evidence' : ''}
                        </span>
                        <div className="mini-bar">
                          {states.map((state) => (
                            <i
                              key={state}
                              style={{
                                width: `${aspect.mentions ? (100 * aspect[state]) / aspect.mentions : 0}%`,
                                background: colors[state],
                              }}
                              title={`${state}: ${aspect[state]}`}
                            />
                          ))}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="panel-footnote">
        <CircleHelp size={14} />
        Neutral and mixed opinions are included in the denominator. Review periods and conditions
        may differ; these results describe the selected corpus.
      </div>
    </section>
  )
}

export default CompareView
