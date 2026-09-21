// src/components/common/ThemeToggle.tsx

import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className = '', showLabel = true }) => {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border font-mono text-[10px] tracking-wider uppercase transition-all select-none backdrop-blur-md ${
        isDark
          ? 'bg-[#13151b]/80 border-white/[0.08] text-neutral-300 hover:text-white hover:border-white/[0.18]'
          : 'bg-white/85 border-neutral-300 text-neutral-700 hover:text-neutral-950 hover:border-neutral-400 shadow-sm'
      } ${className}`}
    >
      {isDark ? (
        <Sun className="w-3.5 h-3.5 text-amber-400 shrink-0" />
      ) : (
        <Moon className="w-3.5 h-3.5 text-neutral-700 shrink-0" />
      )}
      {showLabel && <span>{isDark ? 'LIGHT' : 'DARK'}</span>}
    </button>
  );
};
