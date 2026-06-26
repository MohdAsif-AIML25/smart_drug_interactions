import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { History, Download, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { format } from 'date-fns';
import { getHistory } from '../services/api';
import { SeverityBadge } from './SeverityBadge';

export function HistorySidebar() {
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['history'],
    queryFn: getHistory,
    refetchInterval: 10000,       // poll every 10s as background safety net
    refetchOnWindowFocus: true,   // refresh when user switches back to tab
  });

  const exportPDF = (id: string) => {
    // In production: call backend PDF export endpoint
    window.print();
  };

  return (
    <div className="card h-full">
      <div className="p-6 border-b border-surface-border">
        <div className="flex items-center gap-2">
          <History size={16} className="text-brand-500" />
          <h2 className="font-display font-bold text-white">Query History</h2>
        </div>
        <p className="text-gray-500 text-xs mt-1">Last 10 analyses</p>
      </div>

      <div className="overflow-y-auto max-h-[calc(100vh-200px)]">
        {isLoading && (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-surface-elevated rounded-lg animate-pulse" />
            ))}
          </div>
        )}

        {!isLoading && (!data || data.length === 0) && (
          <div className="p-6 text-center text-gray-500 text-sm font-body">
            No analyses yet. Run your first analysis!
          </div>
        )}

        <div className="p-3 space-y-2">
          {data?.map((item, i) => (
            <motion.div
              key={item.id}
              className="bg-surface-elevated rounded-lg border border-surface-border overflow-hidden"
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <button
                className="w-full p-4 text-left"
                onClick={() =>
                  setExpanded(expanded === item.id ? null : item.id)
                }
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-white font-display">
                      {item.drug_a}
                    </span>
                    <span className="text-gray-500 text-xs">+</span>
                    <span className="text-sm font-semibold text-white font-display">
                      {item.drug_b}
                    </span>
                  </div>
                  {expanded === item.id ? (
                    <ChevronUp size={14} className="text-gray-500" />
                  ) : (
                    <ChevronDown size={14} className="text-gray-500" />
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <SeverityBadge severity={item.severity} size="sm" />
                  <span className="text-xs text-gray-500 font-mono">
                    {format(new Date(item.created_at), 'MMM d, HH:mm')}
                  </span>
                </div>
              </button>

              {expanded === item.id && item.explanation && (
                <motion.div
                  className="px-4 pb-4 border-t border-surface-border"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                >
                  <p className="text-gray-300 text-xs leading-relaxed font-body mt-3 line-clamp-6">
                    {item.explanation}
                  </p>
                  <button
                    onClick={() => exportPDF(item.id)}
                    className="mt-3 flex items-center gap-1.5 text-xs text-brand-500 hover:text-green-400 transition-colors"
                  >
                    <Download size={12} />
                    Export PDF
                  </button>
                </motion.div>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
