import { motion } from 'framer-motion';
import {
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  XCircle,
  Ban,
  HelpCircle,
} from 'lucide-react';
import type { SeverityLevel } from '../types';
import { SEVERITY_CONFIG } from '../types';

interface SeverityBadgeProps {
  severity: SeverityLevel;
  size?: 'sm' | 'md' | 'lg';
}

// Icon per severity level — green/yellow/orange/red/black per spec
const ICONS: Record<SeverityLevel, React.ElementType> = {
  none:            CheckCircle,   // green
  mild:            AlertCircle,   // yellow
  moderate:        AlertTriangle, // orange
  severe:          XCircle,       // red
  contraindicated: Ban,           // black
  unknown:         HelpCircle,    // gray
};

export function SeverityBadge({ severity, size = 'md' }: SeverityBadgeProps) {
  const config = SEVERITY_CONFIG[severity];
  const Icon = ICONS[severity];

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs gap-1',
    md: 'px-3 py-1.5 text-sm gap-1.5',
    lg: 'px-4 py-2 text-base gap-2',
  };

  const iconSize = { sm: 12, md: 14, lg: 16 };

  return (
    <motion.span
      className={`inline-flex items-center rounded-full font-semibold font-display uppercase tracking-wider
        ${config.color} ${config.bg} border ${config.border} ${sizeClasses[size]}`}
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      <Icon size={iconSize[size]} />
      {config.label}
    </motion.span>
  );
}

// ─── Full severity panel with description ─────────────────────────

interface SeverityPanelProps {
  severity: SeverityLevel;
  confidence: number;
  probabilities: Record<string, number>;
}

export function SeverityPanel({ severity, confidence, probabilities }: SeverityPanelProps) {
  const config = SEVERITY_CONFIG[severity];

  // 5-step severity scale
  const SCALE: { key: SeverityLevel; hex: string }[] = [
    { key: 'none',            hex: '#22c55e' },
    { key: 'mild',            hex: '#eab308' },
    { key: 'moderate',        hex: '#f97316' },
    { key: 'severe',          hex: '#ef4444' },
    { key: 'contraindicated', hex: '#111827' },
  ];

  return (
    <motion.div
      className={`card p-6 border ${config.border}`}
      style={{ background: severity === 'contraindicated' ? '#0d0d0d' : undefined }}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-gray-400 text-xs font-display uppercase tracking-wider mb-2">
            Interaction Severity
          </p>
          <SeverityBadge severity={severity} size="lg" />
        </div>
        <div className="text-right">
          <p className="text-gray-400 text-xs font-display uppercase tracking-wider mb-1">
            Confidence
          </p>
          <p className={`text-2xl font-display font-bold ${config.color}`}>
            {(confidence * 100).toFixed(0)}%
          </p>
        </div>
      </div>

      {/* Description */}
      <p className="text-gray-300 text-sm mb-5">{config.description}</p>

      {/* Confidence bar */}
      <div className="mb-5">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Confidence Score</span>
          <span>{(confidence * 100).toFixed(1)}%</span>
        </div>
        <div className="w-full bg-gray-800 rounded-full h-2.5">
          <motion.div
            className="h-2.5 rounded-full"
            style={{ backgroundColor: config.hex }}
            initial={{ width: 0 }}
            animate={{ width: `${confidence * 100}%` }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* 5-level severity scale indicator */}
      <div className="mb-5">
        <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Severity Scale</p>
        <div className="flex gap-1">
          {SCALE.map((step) => (
            <div
              key={step.key}
              className="flex-1 h-3 rounded-sm transition-all duration-300"
              style={{
                backgroundColor: step.hex,
                opacity: step.key === severity ? 1 : 0.2,
                transform: step.key === severity ? 'scaleY(1.4)' : 'scaleY(1)',
              }}
              title={SEVERITY_CONFIG[step.key].label}
            />
          ))}
        </div>
        <div className="flex justify-between text-xs text-gray-600 mt-1">
          <span>None</span>
          <span>Mild</span>
          <span>Moderate</span>
          <span>Severe</span>
          <span>CI</span>
        </div>
      </div>

      {/* Probability breakdown — 5 classes */}
      <div className="grid grid-cols-5 gap-1">
        {SCALE.map(({ key, hex }) => {
          const prob = probabilities[key] ?? 0;
          const isActive = key === severity;
          return (
            <div key={key} className="text-center">
              <div
                className="text-xs font-display uppercase mb-1 truncate"
                style={{ color: isActive ? hex : '#6b7280' }}
              >
                {key === 'contraindicated' ? 'CI' : key}
              </div>
              <div
                className="text-sm font-mono font-bold"
                style={{ color: isActive ? hex : '#9ca3af' }}
              >
                {(prob * 100).toFixed(0)}%
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
