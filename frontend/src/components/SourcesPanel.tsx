import { motion } from 'framer-motion';
import { ExternalLink, BookOpen, Database } from 'lucide-react';
import type { DrugSource } from '../types';

interface SourcesPanelProps {
  sources: DrugSource[];
}

export function SourcesPanel({ sources }: SourcesPanelProps) {
  if (!sources.length) return null;

  return (
    <motion.div
      className="card p-6"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
    >
      <div className="flex items-center gap-2 mb-4">
        <BookOpen size={16} className="text-brand-500" />
        <h3 className="font-display font-semibold text-white text-sm uppercase tracking-wider">
          Sources ({sources.length})
        </h3>
      </div>

      <div className="space-y-3">
        {sources.map((source, i) => (
          <motion.div
            key={i}
            className="bg-surface-elevated rounded-lg p-4 border border-surface-border"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex items-center gap-2">
                <Database size={12} className="text-gray-500 shrink-0 mt-0.5" />
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-display uppercase tracking-wider ${
                    source.source === 'pubmed'
                      ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                      : 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                  }`}
                >
                  {source.source}
                </span>
              </div>

              {source.url && (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-gray-500 hover:text-brand-500 transition-colors shrink-0"
                >
                  <ExternalLink size={14} />
                </a>
              )}
            </div>

            <p className="text-gray-300 text-xs leading-relaxed font-body line-clamp-3">
              {source.snippet}
            </p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
