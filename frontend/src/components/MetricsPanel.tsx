import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { Activity, Clock, Cpu, Database } from 'lucide-react';
import { getHealth } from '../services/api';

// Generate mock time-series data for demo
const generateMetricsData = () => {
  const now = Date.now();
  return Array.from({ length: 20 }, (_, i) => ({
    time: new Date(now - (19 - i) * 30000).toLocaleTimeString(),
    latency: 120 + Math.random() * 80,
    requests: Math.floor(3 + Math.random() * 8),
    mlLatency: 400 + Math.random() * 200,
  }));
};

const MOCK_DATA = generateMetricsData();

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  color?: string;
}

function StatCard({ icon, label, value, sub, color = 'text-brand-500' }: StatCardProps) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className={color}>{icon}</span>
        <span className="text-gray-400 text-xs font-display uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div className={`text-2xl font-display font-bold ${color}`}>{value}</div>
      {sub && <div className="text-gray-500 text-xs mt-1">{sub}</div>}
    </div>
  );
}

export function MetricsPanel() {
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 15000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display font-bold text-white text-xl mb-1">
          System Dashboard
        </h2>
        <p className="text-gray-400 text-sm">Real-time platform metrics</p>
      </div>

      {/* Status row */}
      <div className="flex items-center gap-2 card p-3 px-4">
        <span
          className={`w-2 h-2 rounded-full ${
            health?.status === 'healthy' ? 'bg-brand-500 animate-pulse' : 'bg-red-500'
          }`}
        />
        <span className="text-sm text-gray-300 font-body">
          Platform status:{' '}
          <span className={health?.status === 'healthy' ? 'text-brand-500' : 'text-red-400'}>
            {health?.status ?? 'Checking...'}
          </span>
        </span>
        <span className="ml-auto text-xs text-gray-500 font-mono">v{health?.version ?? '—'}</span>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Activity size={16} />}
          label="Requests / min"
          value="4.2"
          sub="↑ 12% from last hour"
          color="text-brand-500"
        />
        <StatCard
          icon={<Clock size={16} />}
          label="API Latency"
          value="142ms"
          sub="p95: 380ms"
          color="text-blue-400"
        />
        <StatCard
          icon={<Cpu size={16} />}
          label="ML Latency"
          value="498ms"
          sub="avg inference time"
          color="text-purple-400"
        />
        <StatCard
          icon={<Database size={16} />}
          label="Kafka Lag"
          value="0"
          sub="all consumers current"
          color="text-yellow-400"
        />
      </div>

      {/* Request latency chart */}
      <div className="card p-6">
        <h3 className="font-display font-semibold text-white text-sm uppercase tracking-wider mb-4">
          API Request Latency (ms)
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={MOCK_DATA}>
            <defs>
              <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 10, fill: '#6b7280' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#6b7280' }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                background: '#161b22',
                border: '1px solid #30363d',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Area
              type="monotone"
              dataKey="latency"
              stroke="#22c55e"
              strokeWidth={2}
              fill="url(#latencyGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* ML latency chart */}
      <div className="card p-6">
        <h3 className="font-display font-semibold text-white text-sm uppercase tracking-wider mb-4">
          ML Inference Latency (ms)
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={MOCK_DATA}>
            <defs>
              <linearGradient id="mlGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#a855f7" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 10, fill: '#6b7280' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#6b7280' }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                background: '#161b22',
                border: '1px solid #30363d',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Area
              type="monotone"
              dataKey="mlLatency"
              stroke="#a855f7"
              strokeWidth={2}
              fill="url(#mlGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Grafana link */}
      <div className="card p-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-display font-semibold text-white">Grafana Dashboard</p>
          <p className="text-xs text-gray-500 mt-0.5">Full observability stack</p>
        </div>
        <a
          href="http://localhost:3001"
          target="_blank"
          rel="noreferrer"
          className="text-sm btn-primary py-2 px-4"
        >
          Open Grafana →
        </a>
      </div>
    </div>
  );
}
