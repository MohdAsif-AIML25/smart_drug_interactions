/**
 * API Service Layer
 * Centralizes all HTTP calls to the FastAPI backend.
 */

import axios from 'axios';
import type { DrugSuggestion, HistoryItem } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// ─── Drug Search ──────────────────────────────────────────────────

export const searchDrugs = async (query: string): Promise<DrugSuggestion[]> => {
  if (query.length < 2) return [];
  const { data } = await api.get('/drugs/search', { params: { q: query } });
  return data.suggestions ?? [];
};

// ─── Analysis History ──────────────────────────────────────────────

export const getHistory = async (): Promise<HistoryItem[]> => {
  const { data } = await api.get('/history');
  return data.history ?? [];
};

// ─── Health Check ──────────────────────────────────────────────────

export const getHealth = async () => {
  const { data } = await api.get('/health');
  return data;
};

export default api;
