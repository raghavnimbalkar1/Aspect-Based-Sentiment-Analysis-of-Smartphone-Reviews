import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { colors, states, number } from '../api'
import type { Sentiment } from '../api'

function SentimentChart({ totals }: { totals: Record<Sentiment, number> }) {
  const total = Object.values(totals).reduce((a, b) => a + b, 0)
  const data = states.map((state) => ({ name: state, value: totals[state], fill: colors[state] }))
  return (
    <div className="donut-container">
      <ResponsiveContainer width="100%" height={210}>
        <PieChart>
          <Pie
            data={total ? data : [{ name: 'No mentions', value: 1, fill: '#edf0ed' }]}
            dataKey="value"
            innerRadius={66}
            outerRadius={88}
            paddingAngle={total ? 3 : 0}
            stroke="none"
          >
            {(total ? data : [{ fill: '#edf0ed' }]).map((entry, index) => (
              <Cell key={index} fill={entry.fill} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
      <div className="donut-label">
        <strong>{number(total)}</strong>
        <span>feature mentions</span>
      </div>
    </div>
  )
}

export default SentimentChart
