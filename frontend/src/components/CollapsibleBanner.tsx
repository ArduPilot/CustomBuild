import { useState } from 'react';
import { AlertTriangle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

interface CollapsibleBannerProps {
    items: string[];
    message: string;
    color: 'yellow' | 'blue';
    onDismiss: () => void;
    collapseAfter?: number;
}

const COLORS = {
    yellow: {
        border: 'border-yellow-400/30',
        bg: 'bg-yellow-400/5',
        icon: 'text-yellow-400',
        heading: 'text-yellow-300',
        expand: 'text-yellow-400 hover:text-yellow-300',
    },
    blue: {
        border: 'border-blue-400/30',
        bg: 'bg-blue-400/5',
        icon: 'text-blue-400',
        heading: 'text-blue-300',
        expand: 'text-blue-400 hover:text-blue-300',
    },
};

export function CollapsibleBanner({
    items,
    message,
    color,
    onDismiss,
    collapseAfter = 4,
}: CollapsibleBannerProps) {
    const [expanded, setExpanded] = useState(false);
    const c = COLORS[color];
    const collapsible = items.length > collapseAfter;
    const visible = expanded || !collapsible ? items : items.slice(0, collapseAfter);

    return (
        <div
            role={color === 'yellow' ? 'alert' : 'status'}
            className={clsx('rounded-lg border px-4 py-3 text-xs', c.border, c.bg)}
        >
            <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2 flex-1 min-w-0">
                    <AlertTriangle className={clsx('w-3.5 h-3.5 mt-0.5 shrink-0', c.icon)} aria-hidden />
                    <div className="flex-1 min-w-0">
                        <p className={clsx('font-medium mb-1.5', c.heading)}>{message}</p>
                        <ul className="font-mono text-gray-400 space-y-0.5 ml-1">
                            {visible.map(f => (
                                <li key={f}>• {f}</li>
                            ))}
                        </ul>
                        {collapsible && (
                            <button
                                type="button"
                                onClick={() => setExpanded(v => !v)}
                                className={clsx('flex items-center gap-1 mt-2 font-medium transition-colors', c.expand)}
                            >
                                {expanded
                                    ? <><ChevronUp className="w-3 h-3" /> Show less</>
                                    : <><ChevronDown className="w-3 h-3" /> Show {items.length - collapseAfter} more</>
                                }
                            </button>
                        )}
                    </div>
                </div>
                <button
                    type="button"
                    onClick={onDismiss}
                    aria-label="Dismiss"
                    className="text-gray-500 hover:text-gray-300 shrink-0"
                >
                    <XCircle className="w-3.5 h-3.5" />
                </button>
            </div>
        </div>
    );
}
