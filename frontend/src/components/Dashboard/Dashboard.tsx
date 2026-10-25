import React, { useState, useMemo } from 'react';
import axios from 'axios';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts';
import { UploadCloud, FileText, Users, TrendingUp, AlertTriangle, Clock, ChevronUp, ChevronDown } from 'lucide-react';

// --- Type Definitions ---
type Customer = {
  id: number;
  name: string;
  age: number;
  gender: string;
  churn_prob: number;
  tenure: number;
  citytier: number;
  satisfactionscore: number;
  complain: number;
};

type Stats = {
  at_risk: number;
  likely_to_stay: number;
  avg_tenure_churned: number;
  avg_tenure_retained: number;
  churn_rate_by_city: { [key: string]: number };
  complaint_impact: {
    with_complaint: number;
    without_complaint: number;
  };
};

type Segments = {
  "High-Value At-Risk": number;
  "New & Unhappy": number;
  "Loyal Champions": number;
  "New & Promising": number;
  "Other": number;
};

type Insight = {
  title: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  metric: string;
  icon: string;
};

type SortKeys = keyof Customer;

type RecommendedAction = {
  action: string;
  details: string;
  urgency: string;
};

type Recommendation = {
  customer_id: number;
  customer_name: string;
  segment: string;
  churn_probability: number;
  priority: 'critical' | 'high' | 'medium' | 'low';
  recommended_actions: RecommendedAction[];
};

type SegmentStrategy = {
  description: string;
  goal: string;
  key_actions: string[];
  expected_impact: string;
  color: string;
};

type ChurnDriver = {
  driver: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  impact_score: number;
  recommendation: string;
};

type CustomerDriverData = {
  customer_id: number;
  customer_name: string;
  churn_probability: number;
  total_risk_score: number;
  top_drivers: ChurnDriver[];
  driver_count: number;
};

type DriverSummaryItem = {
  name: string;
  affected_customers: number;
  percentage: number;
  avg_churn_prob: number;
  priority: string;
};

type DashboardProps = {
  stats: Stats;
  customers: Customer[];
  segments: Segments;
  insights: Insight[];
  segmentStrategies: { [key: string]: SegmentStrategy };
  driverSummary: { total_customers: number; drivers: DriverSummaryItem[] } | null;
};

// --- Helper Components ---
interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  unit?: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, unit = '' }) => (
    <div className="bg-white p-6 rounded-xl shadow-lg flex items-start">
        <div className="p-3 rounded-lg bg-indigo-100 text-indigo-600 mr-4">
            {icon}
        </div>
        <div>
            <p className="text-sm text-gray-500">{title}</p>
            <p className="text-2xl font-bold text-gray-800">{value}{unit}</p>
        </div>
    </div>
);

const InsightCard: React.FC<{ insight: Insight }> = ({ insight }) => {
  const severityColors = {
    critical: 'bg-red-50 border-red-200 text-red-800',
    high: 'bg-orange-50 border-orange-200 text-orange-800',
    medium: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    low: 'bg-blue-50 border-blue-200 text-blue-800',
  };

  const severityIcons = {
    critical: '🚨',
    high: '⚠️',
    medium: '💡',
    low: 'ℹ️',
  };

  return (
    <div className={`p-4 rounded-lg border-2 ${severityColors[insight.severity]}`}>
      <div className="flex items-start gap-3">
        <span className="text-2xl">{severityIcons[insight.severity]}</span>
        <div className="flex-1">
          <h3 className="font-semibold text-sm mb-1">{insight.title}</h3>
          <p className="text-sm mb-2">{insight.description}</p>
          <p className="text-xs opacity-75">{insight.metric}</p>
        </div>
      </div>
    </div>
  );
};

const StrategyCard: React.FC<{ segment: string; strategy: SegmentStrategy }> = ({ segment, strategy }) => {
  return (
    <div className="bg-white border-2 rounded-xl p-5 shadow-md hover:shadow-lg transition-shadow">
      <div className="flex items-center gap-2 mb-3">
        <div 
          className="w-4 h-4 rounded-full" 
          style={{ backgroundColor: strategy.color }}
        ></div>
        <h3 className="font-bold text-lg text-gray-800">{segment}</h3>
      </div>
      <p className="text-sm text-gray-600 mb-2">{strategy.description}</p>
      <div className="bg-blue-50 rounded-lg p-3 mb-3">
        <p className="text-xs font-semibold text-blue-900 mb-1">Goal:</p>
        <p className="text-sm text-blue-800">{strategy.goal}</p>
      </div>
      <div className="mb-3">
        <p className="text-xs font-semibold text-gray-700 mb-2">Recommended Actions:</p>
        <ul className="space-y-1">
          {strategy.key_actions.map((action, idx) => (
            <li key={idx} className="text-xs text-gray-600 flex items-start">
              <span className="text-green-600 mr-2">✓</span>
              <span>{action}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="bg-green-50 rounded-lg p-2">
        <p className="text-xs font-semibold text-green-900">Expected Impact:</p>
        <p className="text-xs text-green-800">{strategy.expected_impact}</p>
      </div>
    </div>
  );
};

const DriverSummaryCard: React.FC<{ driver: DriverSummaryItem }> = ({ driver }) => {
  const priorityColors = {
    critical: 'bg-red-100 border-red-300 text-red-900',
    high: 'bg-orange-100 border-orange-300 text-orange-900',
    medium: 'bg-yellow-100 border-yellow-300 text-yellow-900',
    low: 'bg-blue-100 border-blue-300 text-blue-900',
  };

  const priorityBadgeColors = {
    critical: 'bg-red-500',
    high: 'bg-orange-500',
    medium: 'bg-yellow-500',
    low: 'bg-blue-500',
  };

  return (
    <div className={`p-4 rounded-lg border-2 ${priorityColors[driver.priority as keyof typeof priorityColors]}`}>
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-bold text-base">{driver.name}</h3>
        <span className={`px-2 py-1 rounded text-xs text-white ${priorityBadgeColors[driver.priority as keyof typeof priorityBadgeColors]}`}>
          {driver.priority.toUpperCase()}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 mt-3">
        <div>
          <p className="text-xs opacity-75">Affected Customers</p>
          <p className="text-xl font-bold">{driver.affected_customers}</p>
        </div>
        <div>
          <p className="text-xs opacity-75">% of Total</p>
          <p className="text-xl font-bold">{driver.percentage}%</p>
        </div>
      </div>
      <div className="mt-3 pt-3 border-t border-current border-opacity-20">
        <p className="text-xs opacity-75">Avg Churn Probability</p>
        <p className="text-lg font-bold">{driver.avg_churn_prob}%</p>
      </div>
    </div>
  );
};

const CustomerDriverBadge: React.FC<{ driver: ChurnDriver }> = ({ driver }) => {
  const severityColors = {
    critical: 'bg-red-100 text-red-800 border-red-300',
    high: 'bg-orange-100 text-orange-800 border-orange-300',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    low: 'bg-blue-100 text-blue-800 border-blue-300',
  };

  return (
    <div className={`p-3 rounded-lg border ${severityColors[driver.severity]} mb-2`}>
      <div className="flex justify-between items-start mb-1">
        <span className="font-semibold text-sm">{driver.driver}</span>
        <span className="text-xs font-bold">Impact: {driver.impact_score}</span>
      </div>
      <p className="text-xs mb-1">{driver.description}</p>
      <p className="text-xs italic opacity-75">→ {driver.recommendation}</p>
    </div>
  );
};

// --- Dashboard Component ---
export default function ChurnDashboard({ stats, customers, segments,insights, segmentStrategies, driverSummary }: DashboardProps) {
  const [sortConfig, setSortConfig] = useState<{ key: SortKeys; direction: string } | null>({ key: 'churn_prob', direction: 'descending' });
  const [activeSegment, setActiveSegment] = useState<string>('All');

  const getCustomerSegment = (customer: Customer): keyof Segments | 'Other' => {
    const { tenure, churn_prob } = customer;
    if (tenure > 12 && churn_prob > 0.6) return "High-Value At-Risk";
    if (tenure <= 3 && churn_prob > 0.6) return "New & Unhappy";
    if (tenure > 12 && churn_prob <= 0.3) return "Loyal Champions";
    if (tenure <= 3 && churn_prob <= 0.3) return "New & Promising";
    return "Other";
  };

  const filteredCustomers = useMemo(() => {
    if (activeSegment === 'All') {
      return customers;
    }
    return customers.filter(c => getCustomerSegment(c) === activeSegment);
  }, [customers, activeSegment]);

  const sortedCustomers = useMemo(() => {
    let sortableItems = [...filteredCustomers];
    if (sortConfig !== null) {
      sortableItems.sort((a, b) => {
        if (a[sortConfig.key] < b[sortConfig.key]) return sortConfig.direction === 'ascending' ? -1 : 1;
        if (a[sortConfig.key] > b[sortConfig.key]) return sortConfig.direction === 'ascending' ? 1 : -1;
        return 0;
      });
    }
    return sortableItems;
  }, [filteredCustomers, sortConfig]);

  const requestSort = (key: SortKeys) => {
    let direction = 'ascending';
    if (sortConfig && sortConfig.key === key && sortConfig.direction === 'ascending') {
      direction = 'descending';
    }
    setSortConfig({ key, direction });
  };

  const getSortIcon = (key: SortKeys) => {
    if (!sortConfig || sortConfig.key !== key) return <ChevronUp className="h-4 w-4 text-gray-400" />;
    return sortConfig.direction === 'ascending' ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />;
  };

  const segmentsData = Object.entries(segments).map(([name, value]) => ({ name, value }));
  const cityChurnData = Object.entries(stats.churn_rate_by_city).map(([tier, rate]) => ({
    name: `Tier ${tier}`,
    "Churn Rate": parseFloat(rate.toFixed(1)),
  }));
  const SEGMENT_COLORS: { [key: string]: string } = {
    "High-Value At-Risk": "#EF4444",
    "New & Unhappy": "#F97316",
    "Loyal Champions": "#22C55E",
    "New & Promising": "#3B82F6",
    "Other": "#6B7280",
  };

  return (
    <div className="p-4 md:p-8 bg-gray-50 min-h-screen font-sans">
      <h1 className="text-3xl font-bold text-gray-800 mb-6">Customer Churn Intelligence</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard title="At Risk" value={stats.at_risk} icon={<AlertTriangle />} unit=" customers" />
        <StatCard title="Avg. Churned Tenure" value={stats.avg_tenure_churned} icon={<Clock />} unit=" months" />
        <StatCard title="Likely to Stay" value={stats.likely_to_stay} icon={<Users />} unit=" customers" />
        <StatCard title="Avg. Retained Tenure" value={stats.avg_tenure_retained} icon={<TrendingUp />} unit=" months" />
      </div>
      {/* AI-Generated Insights Section */}
{insights && insights.length > 0 && (
  <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border-2 border-indigo-200 rounded-xl p-6 shadow-lg mb-8">
    <div className="flex items-center gap-2 mb-4">
      <span className="text-2xl">🤖</span>
      <h2 className="text-xl font-bold text-gray-800">AI-Generated Insights</h2>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {insights.map((insight, idx) => (
        <InsightCard key={idx} insight={insight} />
      ))}
    </div>
  </div>
)}

{/* Churn Driver Summary Section */}
{driverSummary && driverSummary.drivers && driverSummary.drivers.length > 0 && (
  <div className="bg-white border-2 border-red-200 rounded-xl p-6 shadow-lg mb-8">
    <div className="flex items-center gap-2 mb-4">
      <span className="text-2xl">🎯</span>
      <h2 className="text-xl font-bold text-gray-800">Top Churn Drivers Analysis</h2>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {driverSummary.drivers.map((driver, idx) => (
        <DriverSummaryCard key={idx} driver={driver} />
      ))}
    </div>
  </div>
)}

{/* Segment Strategies Section */}
{segmentStrategies && Object.keys(segmentStrategies).length > 0 && (
  <div className="bg-white border-2 border-blue-200 rounded-xl p-6 shadow-lg mb-8">
    <div className="flex items-center gap-2 mb-4">
      <span className="text-2xl">🎯</span>
      <h2 className="text-xl font-bold text-gray-800">Segment-Based Action Plan</h2>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Object.entries(segmentStrategies).map(([segment, strategy]) => (
        <StrategyCard key={segment} segment={segment} strategy={strategy} />
      ))}
    </div>
  </div>
)}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
        <div className="lg:col-span-2 bg-white border rounded-xl p-6 shadow-lg">
          <h2 className="text-xl font-bold mb-4 text-gray-700">Customer Segments</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={segmentsData} onClick={(data) => setActiveSegment(data?.activeLabel || 'All')}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" angle={-15} textAnchor="end" height={50} />
              <YAxis />
              <Tooltip cursor={{fill: 'rgba(239, 246, 255, 0.5)'}} />
              <Bar dataKey="value" name="Customers">
                {segmentsData.map((entry) => (
                  <Cell key={`cell-${entry.name}`} fill={SEGMENT_COLORS[entry.name]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border rounded-xl p-6 shadow-lg">
            <h2 className="text-xl font-bold mb-4 text-gray-700">Churn Rate by City Tier</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={cityChurnData} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" />
                <YAxis unit="%" />
                <Tooltip formatter={(value) => `${value}%`} />
                <Bar dataKey="Churn Rate" fill="#8B5CF6" barSize={40} />
              </BarChart>
            </ResponsiveContainer>
        </div>
      </div>

      <div className="bg-white border rounded-xl p-6 shadow-lg">
        <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-gray-700">Customer Details: <span className="text-indigo-600">{activeSegment}</span></h2>
            {activeSegment !== 'All' && (
                <button onClick={() => setActiveSegment('All')} className="text-sm font-medium text-indigo-600 hover:text-indigo-800">Show All Customers</button>
            )}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            {/* Update the table headers */}
<thead>
  <tr>
    {([
      { key: 'name', label: 'Name' },
      { key: 'churn_prob', label: 'Churn Prob.' },
      { key: 'tenure', label: 'Tenure' },
      { key: 'satisfactionscore', label: 'Satisfaction' },
      { key: 'citytier', label: 'City Tier' },
      { key: 'complain', label: 'Complaints' },
    ] as { key: SortKeys, label: string }[]).map(({ key, label }) => (
      <th key={key} className="px-4 py-3 border-b-2 border-gray-200 text-left text-sm font-medium text-gray-600 cursor-pointer" onClick={() => requestSort(key)}>
        <div className="flex items-center">{label} {getSortIcon(key)}</div>
      </th>
    ))}
    <th className="px-4 py-3 border-b-2 border-gray-200 text-left text-sm font-medium text-gray-600">
      Top Churn Drivers
    </th>
  </tr>
</thead>
            <tbody className="divide-y divide-gray-200">
  {sortedCustomers.map((c) => {
    // Find this customer's drivers
    const customerDrivers = driverSummary ? 
      // You'll need to pass churnDrivers as a prop to display per-customer drivers
      [] : [];
    
    return (
      <tr key={c.id} className="hover:bg-gray-50 transition-colors duration-200">
        <td className="px-4 py-3 whitespace-nowrap">{c.name}</td>
        <td className="px-4 py-3 whitespace-nowrap">
          <span className={`font-bold ${c.churn_prob > 0.7 ? 'text-red-600' : c.churn_prob > 0.5 ? 'text-yellow-600' : 'text-green-600'}`}>
            {(c.churn_prob * 100).toFixed(1)}%
          </span>
        </td>
        <td className="px-4 py-3 whitespace-nowrap">{c.tenure} months</td>
        <td className="px-4 py-3 whitespace-nowrap">{c.satisfactionscore} / 5</td>
        <td className="px-4 py-3 whitespace-nowrap">{c.citytier}</td>
        <td className="px-4 py-3 whitespace-nowrap">
          {c.complain > 0 ? (
            <span className="bg-red-100 text-red-800 px-2 py-1 rounded text-xs font-semibold">
              {c.complain}
            </span>
          ) : (
            <span className="text-green-600">None</span>
          )}
        </td>
        <td className="px-4 py-3">
          <div className="flex flex-wrap gap-1">
            {c.complain >= 1 && (
              <span className="bg-red-100 text-red-800 px-2 py-1 rounded text-xs">Complaints</span>
            )}
            {c.satisfactionscore <= 2 && (
              <span className="bg-orange-100 text-orange-800 px-2 py-1 rounded text-xs">Low Satisfaction</span>
            )}
            {c.tenure < 6 && (
              <span className="bg-yellow-100 text-yellow-800 px-2 py-1 rounded text-xs">Low Usage</span>
            )}
            {c.tenure > 12 && c.satisfactionscore <= 2 && (
              <span className="bg-red-100 text-red-800 px-2 py-1 rounded text-xs">Long Resolution</span>
            )}
          </div>
        </td>
      </tr>
    );
  })}
</tbody>
          </table>
        </div>
      </div>
    </div>
  );
}