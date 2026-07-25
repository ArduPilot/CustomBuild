import { Sun, Moon } from 'lucide-react';

interface ThemeToggleProps {
    isDark: boolean;
    onToggle: () => void;
}

export function ThemeToggle({ isDark, onToggle }: ThemeToggleProps) {
    return (
        <button
            onClick={onToggle}
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="theme-toggle relative flex items-center justify-center w-9 h-9 rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-yellow-400/30"
        >
            {isDark
                ? <Sun className="w-4 h-4" />
                : <Moon className="w-4 h-4" />
            }
        </button>
    );
}
