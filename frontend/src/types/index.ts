// ─── Severity ─────────────────────────────────────────────────────
// 5 classes per project spec — colour-coded green → yellow → orange → red → black

export type SeverityLevel =
  | 'none'
  | 'mild'
  | 'moderate'
  | 'severe'
  | 'contraindicated'
  | 'unknown';

export const SEVERITY_CONFIG: Record<SeverityLevel, {
  label: string;
  color: string;
  bg: string;
  border: string;
  hex: string;
  description: string;
}> = {
  none: {
    label: 'None',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/30',
    hex: '#22c55e',
    description: 'No clinically significant interaction — safe to use together.',
  },
  mild: {
    label: 'Mild',
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/30',
    hex: '#eab308',
    description: 'Minor interaction — generally manageable with standard monitoring.',
  },
  moderate: {
    label: 'Moderate',
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/30',
    hex: '#f97316',
    description: 'Moderate risk — requires careful monitoring and medical awareness.',
  },
  severe: {
    label: 'Severe',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    hex: '#ef4444',
    description: 'High risk — requires immediate medical supervision. Do not use without guidance.',
  },
  contraindicated: {
    label: 'Contraindicated',
    color: 'text-white',
    bg: 'bg-gray-900',
    border: 'border-gray-700',
    hex: '#111827',
    description: 'Dangerous combination — this pair must be avoided. Seek specialist advice immediately.',
  },
  unknown: {
    label: 'Unknown',
    color: 'text-gray-400',
    bg: 'bg-gray-500/10',
    border: 'border-gray-500/30',
    hex: '#6b7280',
    description: 'Insufficient data to assess this interaction.',
  },
};

// ─── API Types ────────────────────────────────────────────────────

export interface DrugSuggestion {
  name: string;
  rxcui?: string;
  generic_name?: string;
}

export interface DrugSource {
  title: string;
  source: string;
  url?: string;
  snippet: string;
}

export interface MLPrediction {
  severity: SeverityLevel;
  confidence: number;
  probabilities: Record<string, number>;
}

export interface AnalyseRequest {
  drug_a: string;
  drug_b: string;
}

export interface HistoryItem {
  id: string;
  drug_a: string;
  drug_b: string;
  severity: SeverityLevel;
  confidence: number;
  explanation?: string;
  created_at: string;
}

// ─── SSE Event Payloads ────────────────────────────────────────────

export interface SeverityEvent {
  severity: SeverityLevel;
  confidence: number;
  probabilities: Record<string, number>;
}

export interface SourcesEvent {
  sources: DrugSource[];
}

export interface TokenEvent {
  token: string;
}

export interface CompleteEvent {
  drug_a: string;
  drug_b: string;
  severity: SeverityLevel;
  full_explanation: string;
}

export interface ErrorEvent {
  message: string;
  code: string;
}

// ─── App State ────────────────────────────────────────────────────

export type AnalysisState =
  | { status: 'idle' }
  | { status: 'loading' }
  | {
      status: 'streaming';
      severity: SeverityLevel;
      confidence: number;
      probabilities: Record<string, number>;
      sources: DrugSource[];
      streamedText: string;
    }
  | {
      status: 'complete';
      severity: SeverityLevel;
      confidence: number;
      probabilities: Record<string, number>;
      sources: DrugSource[];
      explanation: string;
    }
  | { status: 'error'; message: string };
