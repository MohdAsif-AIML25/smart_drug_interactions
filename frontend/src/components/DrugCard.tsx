import { motion } from 'framer-motion';
import { Pill, Info } from 'lucide-react';

interface DrugCardProps {
  name: string;
  role: 'Drug A' | 'Drug B';
  genericName?: string;
}

export function DrugCard({ name, role, genericName }: DrugCardProps) {
  if (!name) return null;

  return (
    <motion.div
      className="card-elevated p-3 flex items-center gap-3"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center shrink-0">
        <Pill size={14} className="text-brand-500" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500 font-display uppercase tracking-wider">{role}</p>
        <p className="text-white font-semibold text-sm truncate">{name}</p>
        {genericName && (
          <p className="text-gray-500 text-xs truncate">{genericName}</p>
        )}
      </div>
      <Info size={13} className="text-gray-600 ml-auto shrink-0" />
    </motion.div>
  );
}
