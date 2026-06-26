/**
 * useSSE Hook
 * Manages Server-Sent Events connection for drug interaction analysis.
 * Parses severity, sources, token, complete, and error events.
 */

import { useCallback, useRef } from 'react';
import type {
  AnalysisState,
  SeverityEvent,
  SourcesEvent,
  TokenEvent,
  CompleteEvent,
  ErrorEvent,
} from '../types';

const SSE_URL = (import.meta.env.VITE_API_URL || '/api/v1') + '/analyse';

interface UseSSEOptions {
  onStateChange: (state: AnalysisState) => void;
}

export function useSSE({ onStateChange }: UseSSEOptions) {
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  const abort = useCallback(() => {
    readerRef.current?.cancel();
    readerRef.current = null;
  }, []);

  const analyse = useCallback(
    async (drugA: string, drugB: string) => {
      abort();
      onStateChange({ status: 'loading' });

      try {
        const response = await fetch(SSE_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ drug_a: drugA, drug_b: drugB }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');
        readerRef.current = reader;

        const decoder = new TextDecoder();
        let buffer = '';

        // Track partial state for streaming updates
        let currentSeverity: SeverityEvent | null = null;
        let currentSources: SourcesEvent | null = null;
        let streamedText = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          let eventType = '';
          let dataLine = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              dataLine = line.slice(6).trim();
            } else if (line === '' && eventType && dataLine) {
              // Parse complete event
              try {
                const payload = JSON.parse(dataLine);

                switch (eventType) {
                  case 'severity': {
                    const ev = payload as SeverityEvent;
                    currentSeverity = ev;
                    onStateChange({
                      status: 'streaming',
                      severity: ev.severity,
                      confidence: ev.confidence,
                      probabilities: ev.probabilities,
                      sources: [],
                      streamedText: '',
                    });
                    break;
                  }

                  case 'sources': {
                    const ev = payload as SourcesEvent;
                    currentSources = ev;
                    if (currentSeverity) {
                      onStateChange({
                        status: 'streaming',
                        severity: currentSeverity.severity,
                        confidence: currentSeverity.confidence,
                        probabilities: currentSeverity.probabilities,
                        sources: ev.sources,
                        streamedText,
                      });
                    }
                    break;
                  }

                  case 'token': {
                    const ev = payload as TokenEvent;
                    streamedText += ev.token;
                    if (currentSeverity) {
                      onStateChange({
                        status: 'streaming',
                        severity: currentSeverity.severity,
                        confidence: currentSeverity.confidence,
                        probabilities: currentSeverity.probabilities,
                        sources: currentSources?.sources ?? [],
                        streamedText,
                      });
                    }
                    break;
                  }

                  case 'complete': {
                    const ev = payload as CompleteEvent;
                    onStateChange({
                      status: 'complete',
                      severity: ev.severity,
                      confidence: currentSeverity?.confidence ?? 0,
                      probabilities: currentSeverity?.probabilities ?? {},
                      sources: currentSources?.sources ?? [],
                      explanation: ev.full_explanation,
                    });
                    break;
                  }

                  case 'error': {
                    const ev = payload as ErrorEvent;
                    onStateChange({ status: 'error', message: ev.message });
                    break;
                  }
                }
              } catch {
                // Ignore malformed SSE data
              }

              eventType = '';
              dataLine = '';
            }
          }
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        onStateChange({ status: 'error', message });
      }
    },
    [abort, onStateChange]
  );

  return { analyse, abort };
}
