import { motion } from 'framer-motion';
import { Activity, Github } from 'lucide-react';

export function Header() {
  return (
    <header className="border-b border-surface-border bg-surface/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <motion.div
          className="flex items-center gap-3"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <div className="w-8 h-8 rounded-lg bg-brand-500/20 border border-brand-500/40 flex items-center justify-center">
            <Activity size={16} className="text-brand-500" />
          </div>
          <div>
            <h1 className="font-display font-bold text-white text-lg leading-none">
              DrugSafe AI
            </h1>
            <p className="text-gray-500 text-xs mt-0.5">
              Understand your medications. Stay safe.
            </p>
          </div>
        </motion.div>

        <nav className="flex items-center gap-6">
          <a
            href="/"
            className="text-sm text-gray-400 hover:text-white transition-colors font-body"
          >
            Analyser
          </a>
          <a
            href="/history"
            className="text-sm text-gray-400 hover:text-white transition-colors font-body"
          >
            History
          </a>
          <a
            href="/dashboard"
            className="text-sm text-gray-400 hover:text-white transition-colors font-body"
          >
            Dashboard
          </a>
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="text-gray-500 hover:text-white transition-colors"
          >
            <Github size={18} />
          </a>
        </nav>
      </div>
    </header>
  );
}
