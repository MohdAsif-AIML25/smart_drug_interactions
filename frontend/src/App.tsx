import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Header } from './components/Header';
import { AnalyseForm } from './components/AnalyseForm';
import { HistorySidebar } from './components/HistorySidebar';
import { MetricsPanel } from './components/MetricsPanel';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 0,
      retry: 2,
    },
  },
});

// ─── Pages ─────────────────────────────────────────────────────────

function AnalyserPage() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2">
        <AnalyseForm />
      </div>
      <div className="lg:col-span-1">
        <HistorySidebar />
      </div>
    </div>
  );
}

function HistoryPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <HistorySidebar />
    </div>
  );
}

function DashboardPage() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <MetricsPanel />
    </div>
  );
}

// ─── App ───────────────────────────────────────────────────────────

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-surface hero-gradient">
          <Header />
          <Routes>
            <Route path="/" element={<AnalyserPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
