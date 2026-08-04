import { type ReactNode, useState, useRef, useEffect } from 'react';
import { Check, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';

interface Step {
    id: string;
    label: string;
}

interface StepHeaderProps {
    steps: Step[];
    currentStep: string;
    onStepClick?: (id: string) => void;
}

export function StepHeader({ steps, currentStep, onStepClick }: StepHeaderProps) {
    const currentIdx = steps.findIndex(s => s.id === currentStep);
    // If currentStep is not in the list (post-flow), treat all as done
    const effectiveIdx = currentIdx === -1 ? steps.length : currentIdx;

    return (
        <div className="flex items-center gap-2 mb-6 flex-wrap">
            {steps.map((step, idx) => {
                const done = idx < effectiveIdx;
                const active = idx === effectiveIdx;
                const clickable = done && !!onStepClick;
                const className = clsx(
                    'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono font-medium transition-all duration-300 border',
                    done && 'bg-yellow-400 border-yellow-400 text-black',
                    active && 'bg-transparent border-yellow-400 text-yellow-400',
                    !done && !active && 'bg-transparent border-surface-4 text-gray-500',
                    clickable && 'cursor-pointer hover:bg-yellow-300 hover:border-yellow-300',
                );
                const content = (
                    <>
                        {done ? (
                            <Check className="w-3 h-3" />
                        ) : (
                            <span className={clsx(
                                'w-4 h-4 rounded-full border flex items-center justify-center text-[10px]',
                                active ? 'border-yellow-400 text-yellow-400' : 'border-gray-500 text-gray-500'
                            )}>{idx + 1}</span>
                        )}
                        {step.label}
                    </>
                );
                return (
                    <div key={step.id} className="flex items-center gap-2">
                        {clickable ? (
                            <button
                                type="button"
                                onClick={() => onStepClick!(step.id)}
                                className={className}
                            >
                                {content}
                            </button>
                        ) : (
                            <div className={className} aria-current={active ? 'step' : undefined}>
                                {content}
                            </div>
                        )}
                        {idx < steps.length - 1 && (
                            <ChevronRight className="w-3 h-3 text-gray-600" />
                        )}
                    </div>
                );
            })}
        </div>
    );
}

interface Option {
    id: string;
    name: string;
}

interface SearchableDropdownProps {
    options: Option[];
    selected?: string;
    onSelect: (id: string) => void;
    placeholder?: string;
    loading?: boolean;
}

export function SearchableDropdown({ options, selected, onSelect, placeholder = 'Select…', loading }: SearchableDropdownProps) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState('');
    const ref = useRef<HTMLDivElement>(null);

    const selectedOpt = options.find(o => o.id === selected);
    const filtered = options.filter(o => o.name.toLowerCase().includes(query.toLowerCase()));

    useEffect(() => {
        function handleClick(e: MouseEvent) {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                setOpen(false);
                setQuery('');
            }
        }
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, []);

    if (loading) return <div className="h-10 bg-skeleton rounded-lg animate-pulse" />;

    return (
        <div ref={ref} className="relative">
            <button
                onClick={() => setOpen(o => !o)}
                className={clsx(
                    'w-full flex items-center justify-between px-4 py-2.5 rounded-lg border text-sm transition-all',
                    selectedOpt
                        ? 'border-yellow-400 bg-yellow-400/5 text-white'
                        : 'border-surface-4 bg-surface-3 text-gray-500 hover:border-yellow-400/30',
                )}
            >
                <span className="truncate font-medium">{selectedOpt ? selectedOpt.name : placeholder}</span>
                <ChevronDown className={clsx('w-4 h-4 shrink-0 ml-2 transition-transform text-gray-500', open && 'rotate-180')} />
            </button>

            {open && (
                <div className="absolute z-50 mt-1 w-full bg-surface-2 border border-surface-4 rounded-lg shadow-xl overflow-hidden">
                    <div className="p-2 border-b border-surface-4">
                        <input
                            autoFocus
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            placeholder="Search…"
                            className="w-full bg-surface-3 border border-surface-4 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 outline-none focus:ring-1 focus:ring-yellow-400/50"
                        />
                    </div>
                    <div className="max-h-60 overflow-y-auto">
                        {filtered.length === 0 ? (
                            <p className="px-4 py-3 text-xs text-gray-500">No results</p>
                        ) : filtered.map(opt => (
                            <button
                                key={opt.id}
                                onClick={() => { onSelect(opt.id); setOpen(false); setQuery(''); }}
                                className={clsx(
                                    'w-full flex items-center justify-between px-4 py-2.5 text-sm text-left transition-colors',
                                    opt.id === selected
                                        ? 'bg-yellow-400/10 text-yellow-400'
                                        : 'text-gray-300 hover:bg-hover',
                                )}
                            >
                                <span>{opt.name}</span>
                                {opt.id === selected && <Check className="w-3 h-3 shrink-0 ml-2" />}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

const FILLER_MESSAGES: Record<'boards' | 'features', string> = {
    boards: 'Loading available boards…',
    features: 'Loading features…',
};

export function LoadingFiller({ kind, loading }: { kind: 'boards' | 'features'; loading: boolean }) {
    if (!loading) return null;

    return (
        <p className="text-xs font-mono mt-3 text-yellow-400 animate-pulse">
            {FILLER_MESSAGES[kind]}
        </p>
    );
}

interface VersionSelectorOption {
    id: string;
    name: string;
    type: 'stable' | 'beta' | 'latest' | 'tag';
    badge?: string;
    badgeColor?: string;
    remote?: string;
}

interface VersionSelectorProps {
    options: VersionSelectorOption[];
    selected?: string;
    onSelect: (id: string) => void;
    loading?: boolean;
}

const QUICK_TYPES = [
    { type: 'stable' as const, label: 'Stable', color: 'badge-green' },
    { type: 'beta' as const, label: 'Beta', color: 'badge-yellow' },
    { type: 'latest' as const, label: 'Latest', color: 'badge-blue' },
];

export function VersionSelector({ options, selected, onSelect, loading }: VersionSelectorProps) {
    const selectedOpt = options.find(o => o.id === selected);

    // One representative per quick type (first match)
    const quickOptions = QUICK_TYPES.map(qt => ({
        ...qt,
        version: options.find(o => o.type === qt.type),
    })).filter(qt => qt.version);

    // Non-quick = selected but not the exact pill representative for its type
    const quickIds = new Set(quickOptions.map(qt => qt.version!.id));
    const isNonQuick = !!selectedOpt && !quickIds.has(selectedOpt.id);

    const [showMore, setShowMore] = useState(isNonQuick);
    const [query, setQuery] = useState('');
    const selectedRowRef = useRef<HTMLButtonElement>(null);

    // Scroll the pre-selected item into view when the dropdown opens on return
    useEffect(() => {
        if (showMore && isNonQuick && selectedRowRef.current) {
            selectedRowRef.current.scrollIntoView({ block: 'nearest' });
        }
    }, [showMore, isNonQuick]);

    const filtered = options.filter(o => o.name.toLowerCase().includes(query.toLowerCase()));

    function toggleMore() {
        setShowMore(v => !v);
        if (showMore) setQuery('');
    }

    function handleSelect(id: string) {
        onSelect(id);
        if (quickIds.has(id)) {
            setShowMore(false);
            setQuery('');
        }
    }

    if (loading) return <div className="h-12 bg-skeleton rounded-lg animate-pulse" />;

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
                {quickOptions.map(({ type, label, color, version }) => (
                    <button
                        key={type}
                        onClick={() => handleSelect(version!.id)}
                        className={clsx(
                            'flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-all',
                            selected === version!.id
                                ? 'border-yellow-400 bg-yellow-400/10 text-white'
                                : 'border-surface-4 bg-surface-3 text-gray-300 hover:border-yellow-400/50 hover:bg-hover hover:text-white',
                        )}
                    >
                        <span className={clsx('badge text-[10px]', color)}>{label}</span>
                        <span className="font-mono text-xs text-gray-400">{version!.name}</span>
                        {selected === version!.id && <Check className="w-3.5 h-3.5 text-yellow-400" />}
                    </button>
                ))}

                <button
                    onClick={toggleMore}
                    className={clsx(
                        'flex items-center gap-1.5 px-4 py-2 rounded-lg border text-sm font-medium transition-all',
                        showMore
                            ? 'border-yellow-400/50 bg-yellow-400/5 text-yellow-400'
                            : 'border-surface-4 bg-surface-3 text-gray-400 hover:border-yellow-400/50 hover:bg-hover hover:text-white',
                    )}
                >
                    {showMore ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    More
                </button>
            </div>

            {showMore && (
                <div className="bg-surface-2 border border-surface-4 rounded-lg overflow-hidden">
                    <div className="p-2 border-b border-surface-4">
                        <input
                            autoFocus
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            placeholder="Search versions…"
                            className="w-full bg-surface-3 border border-surface-4 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 outline-none focus:ring-1 focus:ring-yellow-400/50"
                        />
                    </div>
                    <div className="max-h-56 overflow-y-auto">
                        {filtered.length === 0 ? (
                            <p className="px-4 py-3 text-xs text-gray-500">No results</p>
                        ) : filtered.map(opt => (
                            <button
                                key={opt.id}
                                ref={opt.id === selected ? selectedRowRef : undefined}
                                onClick={() => handleSelect(opt.id)}
                                className={clsx(
                                    'w-full flex items-center justify-between px-4 py-2.5 text-sm text-left transition-colors',
                                    opt.id === selected
                                        ? 'bg-yellow-400/10 text-yellow-400'
                                        : 'text-gray-300 hover:bg-hover',
                                )}
                            >
                                <span>{opt.name}</span>
                                <div className="flex items-center gap-2 shrink-0 ml-2">
                                    {opt.remote && (
                                        <span className="badge text-[10px] badge-gray">{opt.remote}</span>
                                    )}
                                    {opt.badge && (
                                        <span className={clsx('badge text-[10px]', opt.badgeColor ?? 'badge-gray')}>
                                            {opt.badge}
                                        </span>
                                    )}
                                    {opt.id === selected && <Check className="w-3 h-3" />}
                                </div>
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

const PROMOTED_VEHICLE_IDS = ['copter', 'plane', 'rover'] as const;

const VEHICLE_ICONS: Record<string, ReactNode> = {
    copter:     <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><rect x="10" y="10" width="4" height="4" rx="1" /><circle cx="5" cy="5" r="3" /><circle cx="5" cy="5" r="1" fill="currentColor" /><circle cx="19" cy="5" r="3" /><circle cx="19" cy="5" r="1" fill="currentColor" /><circle cx="5" cy="19" r="3" /><circle cx="5" cy="19" r="1" fill="currentColor" /><circle cx="19" cy="19" r="3" /><circle cx="19" cy="19" r="1" fill="currentColor" /><path d="M10 10L7 7M14 10l3-3M10 14l-3 3M14 14l3 3" /></svg>,
    plane:      <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2c-.83 0-1.5.67-1.5 1.5V9L2 14.5V17l8.5-2.5V20l-2 1.5V23l3.5-1 3.5 1v-1.5L13.5 20v-5.5L22 17v-2.5L13.5 9V3.5C13.5 2.67 12.83 2 12 2z" /></svg>,
    rover:      <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><rect x="7" y="3" width="10" height="18" rx="2" /><rect x="3" y="5" width="2" height="4" rx="0.5" /><rect x="3" y="16" width="2" height="4" rx="0.5" /><rect x="19" y="5" width="2" height="4" rx="0.5" /><rect x="19" y="16" width="2" height="4" rx="0.5" /><path d="M5 7h2M17 7h2M5 18h2M17 18h2" /><circle cx="12" cy="7" r="1.5" /><rect x="9" y="11" width="6" height="6" rx="1" /></svg>,
    sub:        <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><path d="M4 11a2 2 0 0 1 2-2h3V6h4v3h3a4 4 0 0 1 0 8H6a2 2 0 0 1-2-2z" /><path d="M11 6V3h2M4 13H2M2 11v4" /><circle cx="15" cy="13" r="1.5" /></svg>,
    tracker:    <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><g transform="translate(12, 15) rotate(35) translate(-12, -15)"><path d="M 4 9 Q 12 21 20 9" /><line x1="12" y1="15" x2="12" y2="5" /><circle cx="12" cy="4" r="2" fill="currentColor" stroke="none" /></g><line x1="12" y1="15" x2="12" y2="21" /><line x1="7" y1="21" x2="17" y2="21" /></svg>,
    heli:       <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><path d="M3 11h5" /><path d="M3 9v4" /><path d="M8 15V11c0-2 2-3 5-3h1c3 0 6 1 6 4c0 2-2 3-4 3H8z" /><path d="M14 5v10" /><path d="M8 5h12" /><path d="M10 15v3" /><path d="M15 15v3" /><path d="M7 18h11a2 2 0 0 0 2-2" /></svg>,
    blimp:      <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10 C22 14 17 15 12 15 C7 15 3 12 3 10 C3 8 7 5 12 5 C17 5 22 6 22 10 Z" /><path d="M6 6.5 L3 3 V8" /><path d="M6 13.5 L3 17 V12" /><path d="M2 10 H8" /><path d="M10 14.8 V16 A1 1 0 0 0 11 17 H13 A1 1 0 0 0 14 16 V14.8" /><path d="M22 10 H23" /></svg>,
    'ap-periph': <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 4V2M12 4V2M16 4V2M8 20v2M12 20v2M16 20v2M2 10h2M20 10h2M2 14h2M20 14h2" /><circle cx="12" cy="12" r="2" /></svg>,
};

const DEFAULT_VEHICLE_ICON = <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>;

interface VehicleSelectorProps {
    options: { id: string; name: string }[];
    selected?: string;
    onSelect: (id: string) => void;
    loading?: boolean;
}

export function VehicleSelector({ options, selected, onSelect, loading }: VehicleSelectorProps) {
    if (loading) {
        return (
            <div className="grid grid-cols-4 gap-2">
                {[...Array(8)].map((_, i) => (
                    <div key={i} className="h-24 bg-skeleton rounded-lg animate-pulse" />
                ))}
            </div>
        );
    }

    const promotedIds = new Set(PROMOTED_VEHICLE_IDS as readonly string[]);
    const promoted = (PROMOTED_VEHICLE_IDS as readonly string[])
        .map(id => options.find(o => o.id === id))
        .filter(Boolean) as { id: string; name: string }[];
    const rest = options.filter(o => !promotedIds.has(o.id));
    const sorted = [...promoted, ...rest];

    return (
        <div className="grid grid-cols-4 gap-2">
            {sorted.map(v => {
                const isSelected = selected === v.id;
                return (
                    <button
                        key={v.id}
                        onClick={() => onSelect(v.id)}
                        className={clsx(
                            'relative flex flex-col items-center justify-center gap-2.5 px-3 py-5 rounded-lg border font-medium transition-all duration-150 group',
                            isSelected
                                ? 'border-yellow-400 bg-yellow-400/10 shadow-[0_0_12px_rgba(250,204,21,0.2)]'
                                : 'border-surface-4 bg-surface-3 hover:border-yellow-400/50 hover:bg-hover',
                        )}
                    >
                        {isSelected && (
                            <span className="absolute top-2 right-2">
                                <Check className="w-3 h-3 text-yellow-400" />
                            </span>
                        )}
                        <span className={clsx(
                            'transition-colors',
                            isSelected ? 'text-yellow-400' : 'text-gray-400 group-hover:text-yellow-400/70',
                        )}>
                            {VEHICLE_ICONS[v.id] ?? DEFAULT_VEHICLE_ICON}
                        </span>
                        <span className={clsx(
                            'text-sm font-semibold leading-tight text-center tracking-wide transition-colors',
                            isSelected ? 'text-yellow-300' : 'text-gray-300 group-hover:text-white',
                        )}>
                            {v.name}
                        </span>
                    </button>
                );
            })}
        </div>
    );
}

export function FormSection({ label, children }: { label: string; children: ReactNode }) {
    return (
        <div className="animate-in">
            <p className="section-title mb-3">{label}</p>
            {children}
        </div>
    );
}

export function ChosenPill({ label, value, onEdit }: { label: string; value: string; onEdit?: () => void }) {
    return (
        <div className="flex items-center gap-2 text-xs mb-4">
            <span className="text-gray-500">{label}:</span>
            <span className="font-mono text-yellow-400">{value}</span>
            {onEdit && (
                <button
                    onClick={onEdit}
                    className="text-gray-500 hover:text-yellow-400 underline underline-offset-2 transition-colors ml-1"
                >
                    change
                </button>
            )}
        </div>
    );
}
