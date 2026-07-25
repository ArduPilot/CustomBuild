import { useState } from 'react';
import { AlertTriangle, X, ChevronRight } from 'lucide-react';
import clsx from 'clsx';
import { ModalShell } from './ModalShell';

export type ConflictKind = 'vehicle' | 'version' | 'board';

interface Option {
    id: string;
    name: string;
    badge?: string;
}

interface ConfigConflictModalProps {
    kind: ConflictKind;
    requested: { id: string; name: string };
    available: Option[];
    onSelect: (id: string) => void;
    onCancel: () => void;
}

const LABELS: Record<ConflictKind, string> = {
    vehicle: 'Vehicle',
    version: 'Firmware version',
    board: 'Board',
};

export function ConfigConflictModal({
    kind,
    requested,
    available,
    onSelect,
    onCancel,
}: ConfigConflictModalProps) {
    const [selected, setSelected] = useState<string | null>(null);
    const [query, setQuery] = useState('');

    const q = query.toLowerCase();
    const filtered = available.filter(o =>
        o.name.toLowerCase().includes(q) || o.id.toLowerCase().includes(q),
    );

    const label = LABELS[kind];

    return (
        <ModalShell
            separateBackdrop
            onClose={onCancel}
            ariaLabelledBy="conflict-modal-title"
            panelClassName="w-full max-w-md bg-surface-2 border border-surface-4 rounded-2xl shadow-2xl max-h-[80vh]"
        >
            <div className="flex items-start justify-between gap-3 px-6 py-5 border-b border-surface-4 shrink-0">
                <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5 shrink-0" />
                    <div>
                        <h2 id="conflict-modal-title" className="text-sm font-semibold text-white">
                            {label} not available
                        </h2>
                        <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                            The config references{' '}
                            <span className="font-mono text-yellow-300">
                                {requested.name}
                            </span>{' '}
                            ({requested.id}), which is not currently listed on the
                            server. Select an alternative to continue.
                        </p>
                    </div>
                </div>
                <button onClick={onCancel} className="btn-ghost p-1 shrink-0 mt-0.5" aria-label="Close">
                    <X className="w-4 h-4" />
                </button>
            </div>

            <div className="flex-1 overflow-hidden flex flex-col px-4 py-3 gap-2">
                <input
                    autoFocus
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    placeholder={`Search ${label.toLowerCase()}…`}
                    className="w-full bg-surface-3 border border-surface-4 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 outline-none focus:ring-1 focus:ring-yellow-400/50 shrink-0"
                />

                <div className="overflow-y-auto flex-1 rounded-lg border border-surface-4">
                    {filtered.length === 0 ? (
                        <p className="px-4 py-6 text-center text-xs text-gray-600">
                            No results
                        </p>
                    ) : (
                        filtered.map(opt => (
                            <button
                                key={opt.id}
                                onClick={() => setSelected(opt.id)}
                                className={clsx(
                                    'w-full flex items-center justify-between px-4 py-3 text-sm transition-colors border-b border-surface-4 last:border-0 text-left',
                                    selected === opt.id
                                        ? 'bg-yellow-400/10 text-yellow-300'
                                        : 'text-gray-300 hover:bg-hover',
                                )}
                            >
                                <span className="min-w-0">
                                    <span className="block truncate">{opt.name}</span>
                                    {opt.id !== opt.name && (
                                        <span className="block font-mono text-[10px] text-gray-500 truncate mt-0.5">
                                            {opt.id}
                                        </span>
                                    )}
                                </span>
                                {opt.badge && (
                                    <span className="badge badge-gray text-[10px] ml-2 shrink-0">
                                        {opt.badge}
                                    </span>
                                )}
                            </button>
                        ))
                    )}
                </div>
            </div>

            <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-surface-4 shrink-0">
                <button onClick={onCancel} className="btn-ghost text-sm px-4 py-2">
                    Cancel
                </button>
                <button
                    disabled={!selected}
                    onClick={() => selected && onSelect(selected)}
                    className="btn-primary text-sm px-5 py-2 disabled:opacity-40"
                >
                    Continue
                    <ChevronRight className="w-4 h-4" />
                </button>
            </div>
        </ModalShell>
    );
}
