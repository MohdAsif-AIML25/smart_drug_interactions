import { motion } from 'framer-motion';
import { Brain } from 'lucide-react';

interface StreamingPanelProps {
  text: string;
  isStreaming: boolean;
}

export function StreamingPanel({ text, isStreaming }: StreamingPanelProps) {
  return (
    <motion.div
      className="card p-6"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
    >
      <div className="flex items-center gap-2 mb-4">
        <Brain size={16} className="text-brand-500" />
        <h3 className="font-display font-semibold text-white text-sm uppercase tracking-wider">
          AI Analysis
        </h3>
        {isStreaming && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-brand-500">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
            Generating...
          </span>
        )}
      </div>

      <div className="text-gray-300 text-sm leading-relaxed font-body min-h-[80px]">
        {text ? (
          <span>
            {text}
            {isStreaming && <span className="streaming-cursor" />}
          </span>
        ) : (
          <div className="space-y-2">
            {[100, 90, 95, 75].map((w, i) => (
              <div
                key={i}
                className="h-3 bg-surface-elevated rounded animate-pulse"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
