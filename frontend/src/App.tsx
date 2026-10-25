import React, { useState, useEffect } from "react";
import axios from "axios";
import UploadCSV from "./components/Upload/Upload";
import Dashboard from "./components/Dashboard/Dashboard";

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

type SegmentStrategy = {
  description: string;
  goal: string;
  key_actions: string[];
  expected_impact: string;
  color: string;
};

type DriverSummaryItem = {
  name: string;
  affected_customers: number;
  percentage: number;
  avg_churn_prob: number;
  priority: string;
};

export default function App() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [segments, setSegments] = useState<Segments | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [segmentStrategies, setSegmentStrategies] = useState<{ [key: string]: SegmentStrategy } | null>(null);
  const [showDashboard, setShowDashboard] = useState(false);
  const [driverSummary, setDriverSummary] = useState<{ total_customers: number; drivers: DriverSummaryItem[] } | null>(null);

  const fetchData = async () => {
    try {
      const [customersRes, statsRes, segmentsRes, insightsRes, strategiesRes, driverSummaryRes] = await Promise.all([
        axios.get("http://127.0.0.1:5000/customers"),
        axios.get("http://127.0.0.1:5000/stats"),
        axios.get("http://127.0.0.1:5000/segments"),
        axios.get("http://127.0.0.1:5000/insights"),
        axios.get("http://127.0.0.1:5000/segment-strategies"),
        axios.get("http://127.0.0.1:5000/driver-summary"),
      ]);
      setCustomers(customersRes.data);
      setStats(statsRes.data);
      setSegments(segmentsRes.data);
      setInsights(insightsRes.data.insights);
      setSegmentStrategies(strategiesRes.data.strategies);
      setDriverSummary(driverSummaryRes.data.summary);
      setShowDashboard(true);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  };

  const handleUploadSuccess = () => {
    fetchData();
  };

  return (
    <div>
      {!showDashboard ? (
        <UploadCSV onUploadSuccess={handleUploadSuccess} />
      ) : (
        stats && segments && segmentStrategies && (
          <Dashboard 
            stats={stats} 
            customers={customers} 
            segments={segments} 
            insights={insights}
            segmentStrategies={segmentStrategies}
            driverSummary={driverSummary}
          />
        )
      )}
    </div>
  );
}
