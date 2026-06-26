import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, ArrowLeftRight, AlertCircle } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { DrugSearch } from './DrugSearch';
import { SeverityPanel } from './SeverityBadge';
import { StreamingPanel } from './StreamingPanel';
import { SourcesPanel } from './SourcesPanel';
import { useSSE } from '../hooks/useSSE';
import type { AnalysisState } from '../types';

export function AnalyseForm() {
  const [drugA, setDrugA] = useState('');
  const [drugB, setDrugB] = useState('');
  const [state, setState] = useState<AnalysisState>({ status: 'idle' });

  const queryClient = useQueryClient();

  const { analyse, abort } = useSSE({
    onStateChange: useCallback((s: AnalysisState) => {
      setState(s);
      // When analysis completes, immediately refresh history sidebar
      if (s.status === 'complete') {
        queryClient.invalidateQueries({ queryKey: ['history'] });
      }
    }, [queryClient]),
  });

  const handleAnalyse = () => {
    if (!drugA.trim() || !drugB.trim()) return;
    analyse(drugA.trim(), drugB.trim());
  };

  const handleSwap = () => {
    setDrugA(drugB);
    setDrugB(drugA);
  };

  const isLoading = state.status === 'loading' || state.status === 'streaming';
  const canAnalyse = drugA.trim().length >= 2 && drugB.trim().length >= 2 && !isLoading;

  return (
    <div className="space-y-6">
      {/* Drug Input Form */}
      <div className="card p-6">
        <h2 className="font-display font-bold text-white text-xl mb-1">
          Drug Interaction Analyser
        </h2>
        <p className="text-gray-400 text-sm mb-6 font-body">
          Enter two drug names to analyse their potential interaction using AI.
        </p>

        <div className="flex items-end gap-3">
          <DrugSearch
            label="First Drug"
            placeholder="e.g. Warfarin"
            value={drugA}
            onChange={setDrugA}
            disabled={isLoading}
          />

          <button
            onClick={handleSwap}
            disabled={isLoading}
            className="mb-0.5 p-3 rounded-lg border border-surface-border bg-surface-elevated
                       hover:border-brand-500/40 text-gray-400 hover:text-brand-500
                       transition-all duration-200 disabled:opacity-40 shrink-0"
            title="Swap drugs"
          >
            <ArrowLeftRight size={16} />
          </button>

          <DrugSearch
            label="Second Drug"
            placeholder="e.g. Aspirin"
            value={drugB}
            onChange={setDrugB}
            disabled={isLoading}
          />
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleAnalyse}
            disabled={!canAnalyse}
            className="btn-primary flex items-center gap-2"
          >
            <Zap size={16} />
            {isLoading ? 'Analysing...' : 'Analyse Interaction'}
          </button>

          {isLoading && (
            <button
              onClick={abort}
              className="text-sm text-gray-500 hover:text-white transition-colors"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      <AnimatePresence mode="wait">
        {state.status === 'loading' && (
          <motion.div
            key="loading"
            className="card p-8 flex items-center justify-center gap-3"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div className="w-5 h-5 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
            <span className="text-gray-400 font-body text-sm">
              Running ML analysis...
            </span>
          </motion.div>
        )}

        {(state.status === 'streaming' || state.status === 'complete') && (
          <motion.div
            key="results"
            className="space-y-4 animate-slide-up"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <SeverityPanel
              severity={state.severity}
              confidence={state.confidence}
              probabilities={state.probabilities}
            />

            <StreamingPanel
              text={
                state.status === 'streaming'
                  ? state.streamedText
                  : state.explanation
              }
              isStreaming={state.status === 'streaming'}
            />

            <SourcesPanel
              sources={
                state.status === 'streaming' ? state.sources : state.sources
              }
            />
          </motion.div>
        )}

        {state.status === 'error' && (
          <motion.div
            key="error"
            className="card p-6 bg-red-500/5 border-red-500/20 flex items-start gap-3"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <AlertCircle size={18} className="text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-red-400 font-display font-semibold text-sm mb-1">
                Analysis Failed
              </p>
              <p className="text-gray-400 text-sm font-body">{state.message}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
