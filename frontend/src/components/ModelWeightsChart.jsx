import React from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from 'recharts';

/** Standardized coefficients of the ranking model: green raises a planet's rank, red lowers it. */
const ModelWeightsChart = ({ data }) => (
  <ResponsiveContainer width="100%" height="100%">
    <BarChart data={data} layout="vertical" margin={{ top: 5, right: 25, left: 110, bottom: 5 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#131c38" horizontal={false} />
      <XAxis
        type="number"
        tick={{ fill: '#94a3b8', fontSize: 11 }}
        axisLine={{ stroke: '#1e293b' }}
      />
      <YAxis
        type="category"
        dataKey="feature"
        tick={{ fill: '#f8fafc', fontSize: 11 }}
        axisLine={{ stroke: '#1e293b' }}
        width={105}
      />
      <Tooltip
        contentStyle={{
          backgroundColor: '#070a16',
          borderColor: '#00d4ff',
          borderRadius: '12px',
          color: '#ffffff',
          fontSize: '12px',
        }}
        formatter={(value, name, item) => [
          `${item.payload.coefficient > 0 ? '+' : ''}${item.payload.coefficient} (${
            item.payload.direction
          })`,
          'Standardized coefficient',
        ]}
      />
      <Bar dataKey="abs_coefficient" radius={[0, 6, 6, 0]}>
        {data.map((entry, index) => (
          <Cell
            key={`cell-${index}`}
            fill={entry.direction === 'positive' ? '#10b981' : '#f43f5e'}
          />
        ))}
      </Bar>
    </BarChart>
  </ResponsiveContainer>
);

export default ModelWeightsChart;
