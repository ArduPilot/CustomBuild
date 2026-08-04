import { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import {
    X, Search, Check, Minus, SlidersHorizontal, AlertTriangle, ChevronDown, ChevronUp, List, Network,
} from 'lucide-react';
import clsx from 'clsx';
import type { Feature } from '../types';
import {
    buildFeatureMaps,
    collectTransitiveDeps,
    collectTransitiveDependents,
} from '../featureDeps';
import { searchFeatures } from '../featureSearch';
import { ModalShell } from './ModalShell';
import { FeaturesGraphView } from './FeaturesGraphView';

type ViewMode = 'list' | 'graph';

interface FeaturesModalProps {
    features: Feature[];
    selected: Set<string>;
    onDone: (selected: Set<string>) => void;
    onClose: () => void;
}

export function FeaturesModal({ features, selected, onDone, onClose }: FeaturesModalProps) {
    const [localSelected, setLocalSelected] = useState<Set<string>>(new Set(selected));
    const [viewMode, setViewMode] = useState<ViewMode>('list');
    const [search, setSearch] = useState('');
    const [highlightedCat, setHighlightedCat] = useState<string | null>(null);
    const [pendingUncheck, setPendingUncheck] = useState<string | null>(null);
    const catFirstRefsMap = useRef<Map<string, HTMLElement>>(new Map());
    const featureListRef = useRef<HTMLDivElement>(null);
    const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const { forwardDeps, reverseDeps, featureMap } = useMemo(
        () => buildFeatureMaps(features),
        [features],
    );

    const collectAllDeps = useCallback(
        (id: string): Set<string> => collectTransitiveDeps(id, forwardDeps, featureMap),
        [forwardDeps, featureMap],
    );

    const collectAllDependents = useCallback(
        (id: string): Set<string> => collectTransitiveDependents(id, reverseDeps),
        [reverseDeps],
    );

    const grouped = features.reduce<Record<string, { catName: string; features: Feature[] }>>((acc, f) => {
        if (!acc[f.category.id]) acc[f.category.id] = { catName: f.category.name, features: [] };
        acc[f.category.id].features.push(f);
        return acc;
    }, {});

    const firstFeaturePerCat = useMemo(() => {
        const map = new Map<string, string>();
        features.forEach(f => { if (!map.has(f.category.id)) map.set(f.category.id, f.id); });
        return map;
    }, [features]);

    const visibleFeatures = useMemo(
        () => (search.trim() ? searchFeatures(features, search) : features),
        [features, search],
    );

    function toggle(id: string) {
        if (localSelected.has(id)) {
            if (pendingUncheck === id) {
                const dependents = collectAllDependents(id);
                setLocalSelected(prev => {
                    const next = new Set(prev);
                    next.delete(id);
                    dependents.forEach(d => next.delete(d));
                    return next;
                });
                setPendingUncheck(null);
            } else {
                const dependents = collectAllDependents(id);
                const activeDependents = [...dependents].filter(d => localSelected.has(d));
                if (activeDependents.length > 0) {
                    setPendingUncheck(id);
                } else {
                    setLocalSelected(prev => { const next = new Set(prev); next.delete(id); return next; });
                    setPendingUncheck(null);
                }
            }
        } else {
            const deps = collectAllDeps(id);
            setLocalSelected(prev => {
                const next = new Set(prev);
                next.add(id);
                deps.forEach(d => next.add(d));
                return next;
            });
            if (pendingUncheck === id) setPendingUncheck(null);
        }
    }

    /** Graph view: deps are visible, so uncheck immediately removes dependents too. */
    function toggleGraph(id: string) {
        if (localSelected.has(id)) {
            const dependents = collectAllDependents(id);
            setLocalSelected(prev => {
                const next = new Set(prev);
                next.delete(id);
                dependents.forEach(d => next.delete(d));
                return next;
            });
            if (pendingUncheck === id) setPendingUncheck(null);
        } else {
            const deps = collectAllDeps(id);
            setLocalSelected(prev => {
                const next = new Set(prev);
                next.add(id);
                deps.forEach(d => next.add(d));
                return next;
            });
            if (pendingUncheck === id) setPendingUncheck(null);
        }
    }

    function cancelPendingUncheck() {
        setPendingUncheck(null);
    }

    function scrollToCategory(catId: string) {
        const el = catFirstRefsMap.current.get(catId);
        const container = featureListRef.current;
        if (el && container) {
            const smooth = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            const top = el.getBoundingClientRect().top
                - container.getBoundingClientRect().top
                + container.scrollTop;
            container.scrollTo({ top, behavior: smooth ? 'smooth' : 'auto' });
        }
        if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
        setHighlightedCat(catId);
        highlightTimeoutRef.current = setTimeout(() => setHighlightedCat(null), 1800);
    }

    function toggleAllInCat(catId: string, catFeatures: Feature[]) {
        const ids = catFeatures.map(f => f.id);
        const allSelected = ids.every(id => localSelected.has(id));

        if (allSelected) {
            const toRemove = new Set(ids);
            ids.forEach(id => collectAllDependents(id).forEach(d => toRemove.add(d)));
            setLocalSelected(prev => {
                const next = new Set(prev);
                toRemove.forEach(id => next.delete(id));
                return next;
            });
            if (pendingUncheck && toRemove.has(pendingUncheck)) setPendingUncheck(null);
        } else {
            const toAdd = new Set(ids);
            ids.forEach(id => collectAllDeps(id).forEach(d => toAdd.add(d)));
            setLocalSelected(prev => {
                const next = new Set(prev);
                toAdd.forEach(id => next.add(id));
                return next;
            });
        }
    }

    function toggleAll() {
        const allSelected = features.every(f => localSelected.has(f.id));
        setLocalSelected(allSelected ? new Set() : new Set(features.map(f => f.id)));
        setPendingUncheck(null);
    }

    const totalCount = features.length;
    const selectedCount = localSelected.size;

    return (
        <ModalShell
            onClose={onClose}
            ariaLabelledBy="features-modal-title"
            panelClassName="w-full max-w-5xl h-[88vh] max-h-[88vh] bg-surface-1 border border-surface-4 rounded-2xl shadow-yellow-lg"
        >
                <div className="flex items-center justify-between gap-3 px-6 py-4 border-b border-surface-4 shrink-0">
                    <div className="flex items-center gap-3 min-w-0 flex-wrap">
                        <SlidersHorizontal className="w-4 h-4 text-yellow-400 shrink-0" />
                        <h2 id="features-modal-title" className="text-lg font-semibold text-white">Select Features</h2>
                        <span className="text-xs text-gray-500 font-mono">{selectedCount} / {totalCount} enabled</span>
                        <div
                            className="flex items-center rounded-lg border border-surface-4 bg-surface-2 p-0.5 ml-1"
                            role="group"
                            aria-label="Feature view mode"
                        >
                            <button
                                type="button"
                                onClick={() => setViewMode('list')}
                                className={clsx(
                                    'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors',
                                    viewMode === 'list'
                                        ? 'bg-surface-3 text-yellow-300 shadow-sm'
                                        : 'text-gray-500 hover:text-gray-300',
                                )}
                                aria-pressed={viewMode === 'list'}
                            >
                                <List className="w-3.5 h-3.5" />
                                List
                            </button>
                            <button
                                type="button"
                                onClick={() => setViewMode('graph')}
                                className={clsx(
                                    'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors',
                                    viewMode === 'graph'
                                        ? 'bg-surface-3 text-yellow-300 shadow-sm'
                                        : 'text-gray-500 hover:text-gray-300',
                                )}
                                aria-pressed={viewMode === 'graph'}
                            >
                                <Network className="w-3.5 h-3.5" />
                                Graph
                            </button>
                        </div>
                    </div>
                    <button onClick={onClose} className="btn-ghost p-2 shrink-0" aria-label="Close">
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {viewMode === 'list' ? (
                <div className="flex flex-col md:flex-row flex-1 min-h-0">
                    <div className="md:w-72 shrink-0 flex flex-col border-b md:border-b-0 md:border-r border-surface-4 bg-surface-2/40 max-h-40 md:max-h-none">
                        <div className="flex items-center px-4 pt-3 pb-2 md:pt-4 md:pb-3 shrink-0">
                            <div className="flex items-center gap-2">
                                <TriStateCheckbox
                                    checked={selectedCount === totalCount}
                                    indeterminate={selectedCount > 0 && selectedCount < totalCount}
                                    onToggle={toggleAll}
                                    label="Toggle all features"
                                />
                                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">All Features</span>
                            </div>
                        </div>
                        <div className="flex-1 overflow-x-auto md:overflow-y-auto md:overflow-x-hidden px-3 pb-3 md:pb-4">
                            <div className="flex md:flex-col gap-2 min-w-min md:min-w-0">
                                {Object.entries(grouped).map(([catId, { catName, features: catFeatures }]) => {
                                    const selCount = catFeatures.filter(f => localSelected.has(f.id)).length;
                                    return (
                                        <CategoryCard
                                            key={catId}
                                            catId={catId}
                                            catName={catName}
                                            total={catFeatures.length}
                                            selectedCount={selCount}
                                            isHighlighted={highlightedCat === catId}
                                            onScrollTo={scrollToCategory}
                                            onToggleAll={() => toggleAllInCat(catId, catFeatures)}
                                        />
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    <div className="flex-1 flex flex-col min-w-0 min-h-0">
                        <div className="px-4 py-3 border-b border-surface-4 shrink-0">
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                                <input
                                    className="input-base pl-9 w-full"
                                    placeholder="Search features…"
                                    value={search}
                                    onChange={e => setSearch(e.target.value)}
                                />
                                {search && (
                                    <button
                                        onClick={() => setSearch('')}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                                    >
                                        <X className="w-3.5 h-3.5" />
                                    </button>
                                )}
                            </div>
                        </div>

                        <div ref={featureListRef} className="flex-1 overflow-y-auto">
                            {visibleFeatures.length === 0 ? (
                                <p className="text-gray-500 text-sm text-center py-12">No features match</p>
                            ) : (
                                <div className="divide-y divide-surface-4">
                                    {visibleFeatures.map(f => {
                                        const activeDependents = pendingUncheck === f.id
                                            ? [...collectAllDependents(f.id)].filter(d => localSelected.has(d)).map(d => featureMap.get(d)!).filter(Boolean)
                                            : [];
                                        return (
                                            <FeatureRow
                                                key={f.id}
                                                feature={f}
                                                checked={localSelected.has(f.id)}
                                                onToggle={toggle}
                                                catHighlighted={highlightedCat === f.category.id}
                                                pendingUncheck={pendingUncheck === f.id}
                                                activeDependents={activeDependents}
                                                onCancelPendingUncheck={cancelPendingUncheck}
                                                innerRef={firstFeaturePerCat.get(f.category.id) === f.id
                                                    ? (el: HTMLElement | null) => {
                                                        if (el) catFirstRefsMap.current.set(f.category.id, el);
                                                        else catFirstRefsMap.current.delete(f.category.id);
                                                    }
                                                    : undefined
                                                }
                                            />
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
                ) : (
                    <FeaturesGraphView
                        features={features}
                        selected={localSelected}
                        forwardDeps={forwardDeps}
                        reverseDeps={reverseDeps}
                        featureMap={featureMap}
                        onToggle={toggleGraph}
                    />
                )}

                <div className="flex items-center justify-between px-6 py-4 border-t border-surface-4 shrink-0">
                    <button onClick={onClose} className="btn-secondary text-sm py-2">Cancel</button>
                    <button onClick={() => onDone(localSelected)} className="btn-primary text-sm py-2">
                        Done
                    </button>
                </div>
        </ModalShell>
    );
}

function CategoryCard({
    catId, catName, total, selectedCount, isHighlighted, onScrollTo, onToggleAll,
}: {
    catId: string;
    catName: string;
    total: number;
    selectedCount: number;
    isHighlighted: boolean;
    onScrollTo: (id: string) => void;
    onToggleAll: () => void;
}) {
    const hasSelection = selectedCount > 0;
    const allSelected = selectedCount === total;
    const indeterminate = hasSelection && !allSelected;
    return (
        <div
            role="button"
            tabIndex={0}
            onClick={() => onScrollTo(catId)}
            onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onScrollTo(catId);
                }
            }}
            className={clsx(
                'shrink-0 md:w-full rounded-xl px-3.5 py-3 border transition-all duration-150 bg-surface-2 cursor-pointer',
                isHighlighted
                    ? 'border-yellow-400 shadow-[0_0_8px_rgba(250,204,21,0.35)]'
                    : 'border-surface-4 hover:border-yellow-400/40 hover:bg-hover',
            )}
        >
            <div className="flex items-center gap-2.5">
                <TriStateCheckbox
                    checked={allSelected}
                    indeterminate={indeterminate}
                    onToggle={onToggleAll}
                    label={`Toggle all in ${catName}`}
                />
                <span
                    className={clsx(
                        'flex-1 text-left text-sm font-medium leading-snug truncate',
                        isHighlighted ? 'text-yellow-300' : 'text-gray-300',
                    )}
                >
                    {catName}
                </span>
                <span className={clsx(
                    'shrink-0 text-[10px] font-mono rounded-full px-2 py-0.5',
                    hasSelection
                        ? 'bg-yellow-400/20 text-yellow-300'
                        : 'bg-surface-4 text-gray-500',
                )}>
                    {selectedCount}/{total}
                </span>
            </div>
        </div>
    );
}

function TriStateCheckbox({ checked, indeterminate, onToggle, label }: {
    checked: boolean;
    indeterminate: boolean;
    onToggle: () => void;
    label: string;
}) {
    const ariaChecked: boolean | 'mixed' = checked ? true : indeterminate ? 'mixed' : false;
    return (
        <button
            type="button"
            role="checkbox"
            aria-checked={ariaChecked}
            aria-label={label}
            onClick={e => { e.stopPropagation(); onToggle(); }}
            className={clsx(
                'w-4 h-4 rounded border flex items-center justify-center shrink-0 transition-colors',
                checked
                    ? 'bg-yellow-400 border-yellow-400'
                    : indeterminate
                        ? 'bg-yellow-400/20 border-yellow-400/60'
                        : 'border-surface-4 hover:border-gray-500',
            )}
        >
            {checked && <Check className="w-2.5 h-2.5 text-black" aria-hidden />}
            {indeterminate && !checked && <Minus className="w-2.5 h-2.5 text-yellow-300" aria-hidden />}
        </button>
    );
}

function FeatureRow({ feature, checked, onToggle, catHighlighted, innerRef, pendingUncheck, activeDependents, onCancelPendingUncheck }: {
    feature: Feature;
    checked: boolean;
    onToggle: (id: string) => void;
    catHighlighted?: boolean;
    innerRef?: (el: HTMLElement | null) => void;
    pendingUncheck?: boolean;
    activeDependents?: Feature[];
    onCancelPendingUncheck?: () => void;
}) {
    const [expandedDeps, setExpandedDeps] = useState(false);
    const rowRef = useRef<HTMLDivElement | null>(null);

    // Collapse when row scrolls out of view
    useEffect(() => {
        if (!pendingUncheck) return;
        const el = rowRef.current;
        if (!el) return;
        const observer = new IntersectionObserver(
            ([entry]) => { if (!entry.isIntersecting) onCancelPendingUncheck?.(); },
            { threshold: 0 }
        );
        observer.observe(el);
        return () => observer.disconnect();
    }, [pendingUncheck, onCancelPendingUncheck]);

    useEffect(() => {
        if (!pendingUncheck) setExpandedDeps(false);
    }, [pendingUncheck]);

    const TREE_LIMIT = 4;
    const shown = activeDependents?.slice(0, expandedDeps ? undefined : TREE_LIMIT) ?? [];
    const hiddenCount = (activeDependents?.length ?? 0) - TREE_LIMIT;

    function setRef(el: HTMLDivElement | null) {
        rowRef.current = el;
        innerRef?.(el);
    }

    return (
        <div
            ref={setRef}
            className={clsx(
                'transition-colors',
                pendingUncheck
                    ? 'dep-warn-row border-l-2'
                    : checked ? 'bg-yellow-400/5' : 'bg-transparent hover:bg-hover',
            )}
        >
            <label className="flex items-start gap-3 px-5 py-3 cursor-pointer">
                <div
                    className={clsx(
                        'w-4 h-4 rounded border mt-0.5 flex items-center justify-center shrink-0 transition-colors',
                        pendingUncheck
                            ? 'dep-warn-check'
                            : checked ? 'bg-yellow-400 border-yellow-400' : 'border-surface-4',
                    )}
                    onClick={e => { e.preventDefault(); onToggle(feature.id); }}
                >
                    {checked && !pendingUncheck && <Check className="w-3 h-3 text-black" />}
                    {pendingUncheck && <Minus className="w-3 h-3 dep-warn-icon" />}
                </div>
                <input type="checkbox" className="sr-only" checked={checked} onChange={() => onToggle(feature.id)} />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-gray-200">{feature.name}</span>
                        <span
                            className={clsx('cat-pill text-[10px] px-2 py-0.5 rounded-full border font-medium', catHighlighted && 'cat-pill-highlight')}
                        >
                            {feature.category.name}
                        </span>
                        {feature.default.enabled && (
                            <span className="badge-green badge text-[10px]">default on</span>
                        )}
                        {!feature.default.enabled && (
                            <span className="text-[10px] px-2 py-0.5 rounded-full border font-medium"
                                style={{ borderColor: 'rgba(107,114,128,0.25)', color: '#6b7280', background: 'transparent' }}>
                                default off
                            </span>
                        )}
                    </div>
                    {feature.description && (
                        <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{feature.description}</p>
                    )}
                </div>
            </label>

            {pendingUncheck && activeDependents && activeDependents.length > 0 && (
                <div className="dep-warn mx-5 mb-3 rounded-lg border overflow-hidden">
                    <div className="flex items-center gap-2 px-3 pt-2.5 pb-1.5">
                        <AlertTriangle className="dep-warn-icon w-3.5 h-3.5 shrink-0" />
                        <span className="dep-warn-title text-xs font-medium">
                            Disabling this will also disable {activeDependents.length} dependent{activeDependents.length !== 1 ? 's' : ''}:
                        </span>
                    </div>
                    <div className="dep-warn-list px-3 pb-2 font-mono text-[11px] leading-relaxed">
                        {shown.map((dep, i) => {
                            const isLast = i === shown.length - 1 && (expandedDeps || hiddenCount <= 0);
                            return (
                                <div key={dep.id} className="flex items-center gap-1">
                                    <span className="dep-warn-tree select-none">{isLast ? '└──' : '├──'}</span>
                                    <span className="dep-warn-name">{dep.name}</span>
                                    <span className="dep-warn-cat text-[10px] ml-1">{dep.category.name}</span>
                                </div>
                            );
                        })}
                        {!expandedDeps && hiddenCount > 0 && (
                            <div className="flex items-center gap-1">
                                <span className="dep-warn-tree select-none">└──</span>
                                <button
                                    type="button"
                                    onClick={() => setExpandedDeps(true)}
                                    className="dep-warn-more flex items-center gap-1 transition-colors"
                                >
                                    <ChevronDown className="w-3 h-3" />
                                    {hiddenCount} more…
                                </button>
                            </div>
                        )}
                        {expandedDeps && hiddenCount > 0 && (
                            <button
                                type="button"
                                onClick={() => setExpandedDeps(false)}
                                className="dep-warn-less flex items-center gap-1 mt-1 transition-colors"
                            >
                                <ChevronUp className="w-3 h-3" />
                                <span>show less</span>
                            </button>
                        )}
                    </div>
                    <div className="dep-warn-footer flex items-center gap-2 px-3 py-2 border-t">
                        <button
                            type="button"
                            onClick={onCancelPendingUncheck}
                            className="dep-warn-cancel text-xs transition-colors px-2 py-1 rounded"
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            onClick={() => onToggle(feature.id)}
                            className="dep-warn-confirm text-xs transition-colors px-2 py-1 rounded ml-auto"
                        >
                            Disable anyway →
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
