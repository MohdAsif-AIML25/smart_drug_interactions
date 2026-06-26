import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, X, Pill } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { searchDrugs } from '../services/api';
import type { DrugSuggestion } from '../types';

interface DrugSearchProps {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function DrugSearch({
  label,
  placeholder = 'Type a drug name...',
  value,
  onChange,
  disabled = false,
}: DrugSearchProps) {
  const [query, setQuery] = useState(value);
  const [suggestions, setSuggestions] = useState<DrugSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Debounced search
  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    try {
      const results = await searchDrugs(q);
      setSuggestions(results);
      setOpen(results.length > 0);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => doSearch(query), 300);
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [query, doSearch]);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const select = (drug: DrugSuggestion) => {
    setQuery(drug.name);
    onChange(drug.name);
    setOpen(false);
    setSuggestions([]);
  };

  const clear = () => {
    setQuery('');
    onChange('');
    setSuggestions([]);
    setOpen(false);
  };

  return (
    <div ref={wrapperRef} className="relative w-full">
      <label className="block text-xs font-display uppercase tracking-wider text-gray-400 mb-2">
        {label}
      </label>

      <div className="relative">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
        />

        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            onChange(e.target.value);
          }}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder={placeholder}
          disabled={disabled}
          className="input-field pl-9 pr-9"
          autoComplete="off"
        />

        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin" />
          </div>
        )}

        {!loading && query && (
          <button
            onClick={clear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white transition-colors"
          >
            <X size={14} />
          </button>
        )}
      </div>

      <AnimatePresence>
        {open && suggestions.length > 0 && (
          <motion.ul
            className="absolute z-50 w-full mt-1 card-elevated border border-surface-border rounded-lg overflow-hidden shadow-2xl"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
          >
            {suggestions.slice(0, 8).map((drug, i) => (
              <li key={i}>
                <button
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-surface-border transition-colors text-left"
                  onClick={() => select(drug)}
                >
                  <Pill size={14} className="text-brand-500 shrink-0" />
                  <span className="text-sm text-white font-body">{drug.name}</span>
                  {drug.generic_name && (
                    <span className="text-xs text-gray-500 ml-auto">{drug.generic_name}</span>
                  )}
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
