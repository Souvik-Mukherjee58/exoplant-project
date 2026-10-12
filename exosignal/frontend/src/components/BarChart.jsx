import React from 'react'

const BarChart = ({ data, labelField, valueField, color, title, formatValue, maxValueOverride }) => {
  const maxValue = maxValueOverride || Math.max(...data.map(d => d[valueField])) || 100

  return (
    <div className="bg-space-darker rounded-lg border border-exosignal-blue/20 p-6">
      {title && <h3 className="text-lg font-semibold text-exosignal-text mb-4">{title}</h3>}
      <div className="space-y-3">
        {data.map((item, index) => {
          const value = typeof item[valueField] === 'number' ? item[valueField] : 0
          const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0

          return (
            <div key={index} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-exosignal-text font-medium">{item[labelField]}</span>
                <span className="text-exosignal-text/70">
                  {formatValue ? formatValue(value) : value}
                </span>
              </div>
              <div className="w-full bg-exosignal-blue/10 rounded-full h-3">
                <div
                  className={`h-3 rounded-full ${color}`}
                  style={{ width: `${percentage}%` }}
                ></div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default BarChart