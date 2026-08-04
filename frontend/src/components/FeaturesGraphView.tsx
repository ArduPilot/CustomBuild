import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
    type MouseEvent as ReactMouseEvent,
} from 'react';
import { createPortal } from 'react-dom';
import {
    ReactFlow,
    Background,
    BaseEdge,
    MarkerType,
    Position,
    Handle,
    getBezierPath,
    useReactFlow,
    ReactFlowProvider,
    useNodesState,
    useEdgesState,
    useStore,
    type Node,
    type Edge,
    type EdgeProps,
    type NodeProps,
    BackgroundVariant,
} from '@xyflow/react';
import {
    Search, X, Check, EyeOff, Eye, ZoomIn, ZoomOut, LayoutGrid, Scan,
} from 'lucide-react';
import clsx from 'clsx';
import type { Feature } from '../types';
import {
    collectTransitiveDeps,
    collectTransitiveDependents,
    reducedDependencyEdges,
} from '../featureDeps';
import { searchFeatures } from '../featureSearch';
import '@xyflow/react/dist/style.css';

const NODE_WIDTH = 220;
const NODE_HEIGHT = 64;
const MIN_ZOOM = 0.02;
const MAX_ZOOM = 2;
const RANK_SEP = 180;
const NODE_GAP = 24;
const ROOT_GAP = 40;
const STANDALONE_GAP_Y = 48;
const FIT_PADDING = 0.12;
const INFO_CARD_DELAY_MS = 500;
const INFO_CARD_WIDTH = 280;
const INFO_CARD_GAP = 8;
const INFO_CARD_EST_H = 148;

interface FeatureNodeData extends Record<string, unknown> {
    feature: Feature;
    searchHighlight: boolean;
    focused: boolean; // Subtree-view root
    dimmed: boolean;
    treeActive: boolean;
    onFocus: (id: string) => void;
    onShowAll: () => void;
}

interface FeatureEdgeData extends Record<string, unknown> {
    treeActive: boolean;
    dimmed: boolean;
}

const HANDLE_CLASS = '!w-2 !h-2 !bg-gray-500 !border-0 !pointer-events-none';

interface SelectionCtx {
    selected: Set<string>;
    onToggle: (id: string) => void;
}

const FeatureGraphSelectionContext = createContext<SelectionCtx | null>(null);

function useSelection() {
    const ctx = useContext(FeatureGraphSelectionContext);
    if (!ctx) throw new Error('FeatureGraphSelectionContext missing');
    return ctx;
}

function FeatureEdge({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    data,
    markerEnd,
    style,
}: EdgeProps<Edge<FeatureEdgeData>>) {
    const treeActive = data?.treeActive ?? false;
    const dimmed = data?.dimmed ?? false;

    const [path] = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition: Position.Left,
        targetX,
        targetY,
        targetPosition: Position.Right,
    });
    const stroke = treeActive
        ? 'rgb(250, 204, 21)'
        : 'rgb(107, 114, 128)';

    return (
        <BaseEdge
            id={id}
            path={path}
            markerEnd={markerEnd}
            style={{
                ...style,
                stroke,
                strokeWidth: treeActive ? 2.25 : 1.25,
                opacity: dimmed ? 0.12 : 1,
                transition: 'opacity 150ms, stroke 150ms',
            }}
        />
    );
}

function FeatureGraphNode({ data }: NodeProps<Node<FeatureNodeData>>) {
    const {
        feature, searchHighlight, focused, dimmed, treeActive, onFocus, onShowAll,
    } = data;
    const { selected, onToggle } = useSelection();
    const checked = selected.has(feature.id);

    function handleToggle(e: ReactMouseEvent) {
        e.preventDefault();
        e.stopPropagation();
        onToggle(feature.id);
    }

    function handleCardClick(e: ReactMouseEvent) {
        e.preventDefault();
        e.stopPropagation();
        if (focused) onShowAll();
        else onFocus(feature.id);
    }

    return (
        <div
            className={clsx(
                'rounded-xl border px-3 py-2 shadow-sm transition-colors duration-200 w-[220px] nopan cursor-pointer',
                dimmed
                    ? 'bg-surface-1 border-surface-3 text-gray-600'
                    : focused
                        ? 'bg-yellow-400/25 border-yellow-400'
                        : searchHighlight || treeActive
                            ? 'bg-surface-3 border-yellow-400 shadow-[0_0_14px_rgba(250,204,21,0.4)] ring-2 ring-yellow-400/40'
                            : checked
                                ? 'bg-surface-3 border-yellow-400/70'
                                : 'bg-surface-2 border-surface-4 hover:border-gray-500',
            )}
            onClick={handleCardClick}
            onMouseDown={(e: ReactMouseEvent) => e.stopPropagation()}
            onPointerDown={(e: ReactMouseEvent) => e.stopPropagation()}
        >
            <Handle type="target" position={Position.Right} className={HANDLE_CLASS} />
            <div className="flex items-start gap-2.5">
                <button
                    type="button"
                    role="checkbox"
                    aria-checked={checked}
                    aria-label={`Toggle ${feature.name}`}
                    onClick={handleToggle}
                    onMouseDown={(e: ReactMouseEvent) => e.stopPropagation()}
                    onPointerDown={(e: ReactMouseEvent) => e.stopPropagation()}
                    className={clsx(
                        'w-4 h-4 rounded border mt-0.5 flex items-center justify-center shrink-0 transition-colors nodrag nopan',
                        checked
                            ? 'bg-yellow-400 border-yellow-400'
                            : 'border-surface-4 hover:border-gray-500 bg-surface-1',
                    )}
                >
                    {checked && <Check className="w-3 h-3 text-black" />}
                </button>
                <div className="min-w-0 flex-1 pointer-events-none">
                    <div
                        className={clsx(
                            'text-sm font-medium truncate leading-snug',
                            dimmed ? 'text-gray-600' : 'text-gray-200',
                        )}
                    >
                        {feature.name}
                    </div>
                    <div
                        className={clsx(
                            'text-[10px] truncate mt-0.5',
                            dimmed
                                ? 'text-gray-700'
                                : focused
                                    ? 'text-gray-300'
                                    : 'text-gray-500',
                        )}
                    >
                        {feature.category.name}
                    </div>
                </div>
            </div>
            <Handle type="source" position={Position.Left} className={HANDLE_CLASS} />
        </div>
    );
}

const nodeTypes = { feature: FeatureGraphNode };
const edgeTypes = { feature: FeatureEdge };

function isStandalone(
    id: string,
    forwardDeps: Map<string, Set<string>>,
    reverseDeps: Map<string, Set<string>>,
): boolean {
    const outs = forwardDeps.get(id);
    const ins = reverseDeps.get(id);
    return (!outs || outs.size === 0) && (!ins || ins.size === 0);
}

/** Ancestors + self + descendants for hover/focus trees. */
function relatedTreeIds(
    id: string,
    forwardDeps: Map<string, Set<string>>,
    reverseDeps: Map<string, Set<string>>,
    featureMap: Map<string, Feature>,
): Set<string> {
    const deps = collectTransitiveDeps(id, forwardDeps, featureMap);
    const dependents = collectTransitiveDependents(id, reverseDeps);
    const set = new Set<string>([id]);
    deps.forEach(d => set.add(d));
    dependents.forEach(d => set.add(d));
    return set;
}

/** Longest-path column rank: roots = 0; else 1 + max(dep ranks). */
function computeRanks(
    connectedIds: Set<string>,
    forwardDeps: Map<string, Set<string>>,
): Map<string, number> {
    const ranks = new Map<string, number>();
    const visiting = new Set<string>();

    function rankOf(id: string): number {
        const cached = ranks.get(id);
        if (cached !== undefined) return cached;
        if (visiting.has(id)) return 0;
        visiting.add(id);

        let maxDep = -1;
        for (const depId of forwardDeps.get(id) ?? []) {
            if (!connectedIds.has(depId)) continue;
            maxDep = Math.max(maxDep, rankOf(depId));
        }
        visiting.delete(id);

        const r = maxDep < 0 ? 0 : maxDep + 1;
        ranks.set(id, r);
        return r;
    }

    for (const id of connectedIds) rankOf(id);
    return ranks;
}

/**
 * Primary layout parent = dependency with maximum rank (deepest / rightmost).
 * Matches longest-path columns so packing stays under the deepest dep.
 */
function buildLayoutChildren(
    connectedIds: Set<string>,
    forwardDeps: Map<string, Set<string>>,
    ranks: Map<string, number>,
): { children: Map<string, string[]>; roots: string[] } {
    const children = new Map<string, string[]>();
    const roots: string[] = [];

    const sortedIds = [...connectedIds].sort((a, b) => a.localeCompare(b));

    for (const id of sortedIds) {
        const inSetDeps = [...(forwardDeps.get(id) ?? [])].filter(d => connectedIds.has(d));
        if (inSetDeps.length === 0) {
            roots.push(id);
            continue;
        }

        // Prefer deepest (highest rank) dependency as layout parent
        inSetDeps.sort((a, b) => {
            const rd = (ranks.get(b) ?? 0) - (ranks.get(a) ?? 0);
            return rd !== 0 ? rd : a.localeCompare(b);
        });
        const parent = inSetDeps[0];
        if (!children.has(parent)) children.set(parent, []);
        children.get(parent)!.push(id);
    }

    for (const [, kids] of children) {
        kids.sort((a, b) => a.localeCompare(b));
    }
    roots.sort((a, b) => a.localeCompare(b));

    return { children, roots };
}

function computeSubtreeHeights(
    roots: string[],
    children: Map<string, string[]>,
): Map<string, number> {
    const heights = new Map<string, number>();

    function heightOf(id: string): number {
        const cached = heights.get(id);
        if (cached !== undefined) return cached;
        const kids = children.get(id) ?? [];
        let h: number;
        if (kids.length === 0) {
            h = NODE_HEIGHT;
        } else {
            const sum = kids.reduce((acc, k) => acc + heightOf(k), 0);
            h = Math.max(sum + NODE_GAP * (kids.length - 1), NODE_HEIGHT);
        }
        heights.set(id, h);
        return h;
    }

    for (const r of roots) heightOf(r);
    return heights;
}

function placeTree(
    id: string,
    top: number,
    ranks: Map<string, number>,
    children: Map<string, string[]>,
    heights: Map<string, number>,
    positions: Map<string, { x: number; y: number }>,
): void {
    const kids = children.get(id) ?? [];
    const blockH = heights.get(id) ?? NODE_HEIGHT;
    const rank = ranks.get(id) ?? 0;
    const x = rank * (NODE_WIDTH + RANK_SEP);

    if (kids.length === 0) {
        positions.set(id, { x, y: top });
        return;
    }

    let cursor = top;
    for (const kid of kids) {
        placeTree(kid, cursor, ranks, children, heights, positions);
        cursor += (heights.get(kid) ?? NODE_HEIGHT) + NODE_GAP;
    }

    const firstKid = positions.get(kids[0])!;
    const lastKid = positions.get(kids[kids.length - 1])!;
    const y = (firstKid.y + lastKid.y + NODE_HEIGHT) / 2 - NODE_HEIGHT / 2;
    const minY = top;
    const maxY = top + blockH - NODE_HEIGHT;
    positions.set(id, { x, y: Math.min(maxY, Math.max(minY, y)) });
}

function buildLayout(
    features: Feature[],
    forwardDeps: Map<string, Set<string>>,
    reverseDeps: Map<string, Set<string>>,
    hideStandalone: boolean,
): {
    positions: Map<string, { x: number; y: number }>;
    visible: Feature[];
    edgePairs: Array<{ source: string; target: string }>;
} {
    const connected = features.filter(f => !isStandalone(f.id, forwardDeps, reverseDeps));
    const standalones = hideStandalone
        ? []
        : features.filter(f => isStandalone(f.id, forwardDeps, reverseDeps));

    const connectedIds = new Set(connected.map(f => f.id));
    const positions = new Map<string, { x: number; y: number }>();
    // Graph edges: covering only (selection still uses full forwardDeps)
    const edgePairs = reducedDependencyEdges(connectedIds, forwardDeps);

    if (connected.length > 0) {
        const ranks = computeRanks(connectedIds, forwardDeps);
        const { children, roots } = buildLayoutChildren(connectedIds, forwardDeps, ranks);
        const heights = computeSubtreeHeights(roots, children);

        let cursor = 0;
        for (const root of roots) {
            placeTree(root, cursor, ranks, children, heights, positions);
            cursor += (heights.get(root) ?? NODE_HEIGHT) + ROOT_GAP;
        }

        for (const id of connectedIds) {
            if (!positions.has(id)) {
                positions.set(id, { x: 0, y: cursor });
                cursor += NODE_HEIGHT + NODE_GAP;
            }
        }
    }

    if (standalones.length > 0) {
        let maxY = 0;
        if (positions.size > 0) {
            maxY = Math.max(...[...positions.values()].map(p => p.y + NODE_HEIGHT));
        }
        const startY = positions.size > 0 ? maxY + STANDALONE_GAP_Y : 0;
        standalones
            .slice()
            .sort((a, b) => a.name.localeCompare(b.name))
            .forEach((f, i) => {
                positions.set(f.id, {
                    x: 0,
                    y: startY + i * (NODE_HEIGHT + NODE_GAP),
                });
            });
    }

    return { positions, visible: [...connected, ...standalones], edgePairs };
}

function buildFlowElements(
    visible: Feature[],
    positions: Map<string, { x: number; y: number }>,
    edgePairs: Array<{ source: string; target: string }>,
    searchHighlightId: string | null,
    focusedId: string | null,
    hoverTree: Set<string> | null,
    onFocus: (id: string) => void,
    onShowAll: () => void,
): { nodes: Node<FeatureNodeData>[]; edges: Edge<FeatureEdgeData>[] } {
    const hovering = hoverTree !== null && hoverTree.size > 0;

    const nodes: Node<FeatureNodeData>[] = visible.map(f => {
        const pos = positions.get(f.id)!;
        const inTree = hovering && hoverTree!.has(f.id);
        return {
            id: f.id,
            type: 'feature',
            position: pos,
            className: 'nopan nodrag',
            data: {
                feature: f,
                searchHighlight: searchHighlightId === f.id,
                focused: focusedId === f.id,
                dimmed: hovering && !inTree,
                treeActive: !!inTree,
                onFocus,
                onShowAll,
            },
        };
    });

    const edges: Edge<FeatureEdgeData>[] = edgePairs.map(({ source, target }) => {
        const inTree = hovering && hoverTree!.has(source) && hoverTree!.has(target);
        const dimmed = hovering && !inTree;
        const stroke = inTree ? 'rgb(250, 204, 21)' : 'rgb(107, 114, 128)';
        return {
            id: `${source}->${target}`,
            source,
            target,
            type: 'feature',
            data: {
                treeActive: !!inTree,
                dimmed,
            },
            markerEnd: {
                type: MarkerType.ArrowClosed,
                width: 16,
                height: 16,
                color: stroke,
            },
        };
    });

    return { nodes, edges };
}

function ZoomSlider() {
    const { zoomTo, zoomIn, zoomOut, fitView } = useReactFlow();
    const zoom = useStore(s => s.transform[2]);

    return (
        <div className="flex flex-col items-center gap-1 rounded-lg border border-surface-4 bg-surface-2 px-1.5 py-1.5 shadow-sm">
            <button
                type="button"
                onClick={() => zoomIn({ duration: 150 })}
                className="p-1 rounded text-gray-400 hover:text-gray-200 hover:bg-hover transition-colors"
                aria-label="Zoom in"
            >
                <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <input
                type="range"
                min={MIN_ZOOM}
                max={MAX_ZOOM}
                step={0.01}
                value={zoom}
                onChange={e => zoomTo(Number(e.target.value), { duration: 0 })}
                className="features-zoom-slider"
                aria-label="Zoom"
                style={{ writingMode: 'vertical-lr', direction: 'rtl', height: 100, width: 14 }}
            />
            <button
                type="button"
                onClick={() => zoomOut({ duration: 150 })}
                className="p-1 rounded text-gray-400 hover:text-gray-200 hover:bg-hover transition-colors"
                aria-label="Zoom out"
            >
                <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="text-[10px] font-mono text-gray-500 tabular-nums px-0.5">
                {Math.round(zoom * 100)}%
            </span>
            <button
                type="button"
                onClick={() => fitView({
                    padding: FIT_PADDING,
                    minZoom: MIN_ZOOM,
                    maxZoom: MAX_ZOOM,
                    duration: 300,
                })}
                className="p-1 rounded text-gray-400 hover:text-gray-200 hover:bg-hover transition-colors"
                aria-label="Fit graph in view"
                title="Fit to view"
            >
                <Scan className="w-3.5 h-3.5" />
            </button>
        </div>
    );
}

interface FeatureInfoCardState {
    feature: Feature;
    top: number;
    left: number;
}

function placeInfoTooltip(
    nodeRect: DOMRect,
    cardW: number,
    cardH: number,
): { top: number; left: number } {
    return {
        top: nodeRect.top - INFO_CARD_GAP - cardH,
        left: nodeRect.left + nodeRect.width / 2 - cardW / 2,
    };
}

function FeatureInfoCard({ feature, top, left }: FeatureInfoCardState) {
    const showName = feature.name !== feature.id;
    const caretBorder = 'rgb(var(--s4))';

    return createPortal(
        <div
            role="tooltip"
            className="pointer-events-none fixed z-[9999]"
            style={{ top, left, width: INFO_CARD_WIDTH }}
        >
            <div className="relative bg-surface-1 border border-surface-4 rounded-xl shadow-lg px-3.5 py-3 text-left">
                <div className="text-sm font-semibold text-gray-100 font-mono truncate">
                    {feature.id}
                </div>
                {showName && (
                    <div className="text-xs text-gray-400 mt-0.5 truncate">{feature.name}</div>
                )}
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <span className="text-[10px] px-2 py-0.5 rounded-full border border-surface-4 text-gray-400">
                        {feature.category.name}
                    </span>
                    <span
                        className={clsx(
                            'text-[10px] px-2 py-0.5 rounded-full border font-medium',
                            feature.default.enabled
                                ? 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10'
                                : 'border-surface-4 text-gray-500',
                        )}
                    >
                        default {feature.default.enabled ? 'on' : 'off'}
                    </span>
                </div>
                <p className="text-xs text-gray-400 mt-2.5 leading-relaxed">
                    {feature.description?.trim() || 'No description'}
                </p>
                <div
                    aria-hidden
                    className="absolute left-1/2 -translate-x-1/2 -bottom-[5px] w-0 h-0"
                    style={{
                        borderLeft: '5px solid transparent',
                        borderRight: '5px solid transparent',
                        borderTop: `5px solid ${caretBorder}`,
                    }}
                />
            </div>
        </div>,
        document.body,
    );
}

interface FeaturesGraphViewProps {
    features: Feature[];
    selected: Set<string>;
    forwardDeps: Map<string, Set<string>>;
    reverseDeps: Map<string, Set<string>>;
    featureMap: Map<string, Feature>;
    onToggle: (id: string) => void;
}

function FeaturesGraphCanvas({
    features,
    selected,
    forwardDeps,
    reverseDeps,
    featureMap,
    onToggle,
}: FeaturesGraphViewProps) {
    const { fitView } = useReactFlow();
    const [hideStandalone, setHideStandalone] = useState(true);
    const [search, setSearch] = useState('');
    const [searchHighlightId, setSearchHighlightId] = useState<string | null>(null);
    const [hoveredId, setHoveredId] = useState<string | null>(null);
    const [focusedId, setFocusedId] = useState<string | null>(null);
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const [infoCard, setInfoCard] = useState<FeatureInfoCardState | null>(null);
    const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const searchWrapRef = useRef<HTMLDivElement>(null);
    const hoverLeaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const infoCardTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    const clearInfoCard = useCallback(() => {
        if (infoCardTimer.current) {
            clearTimeout(infoCardTimer.current);
            infoCardTimer.current = null;
        }
        setInfoCard(null);
    }, []);

    const onToggleRef = useRef(onToggle);
    onToggleRef.current = onToggle;
    const stableToggle = useCallback((id: string) => onToggleRef.current(id), []);

    const onFocusRef = useRef((id: string) => setFocusedId(id));
    onFocusRef.current = (id: string) => {
        setFocusedId(id);
        setHoveredId(null);
        clearInfoCard();
    };
    const stableFocus = useCallback((id: string) => onFocusRef.current(id), []);

    const showAll = useCallback(() => {
        setFocusedId(null);
        setHoveredId(null);
        clearInfoCard();
    }, [clearInfoCard]);

    const selectionValue = useMemo<SelectionCtx>(
        () => ({ selected, onToggle: stableToggle }),
        [selected, stableToggle],
    );

    const layoutFeatures = useMemo(() => {
        if (!focusedId) return features;
        const tree = relatedTreeIds(focusedId, forwardDeps, reverseDeps, featureMap);
        return features.filter(f => tree.has(f.id));
    }, [features, focusedId, forwardDeps, reverseDeps, featureMap]);

    const layout = useMemo(
        () => buildLayout(
            layoutFeatures,
            forwardDeps,
            reverseDeps,
            // Focus already scopes the set; keep standalones so a lone focused
            // feature still appears.
            focusedId ? false : hideStandalone,
        ),
        [layoutFeatures, forwardDeps, reverseDeps, hideStandalone, focusedId],
    );

    const hoverTree = useMemo(() => {
        if (!hoveredId) return null;
        return relatedTreeIds(hoveredId, forwardDeps, reverseDeps, featureMap);
    }, [hoveredId, forwardDeps, reverseDeps, featureMap]);

    const flowElements = useMemo(
        () =>
            buildFlowElements(
                layout.visible,
                layout.positions,
                layout.edgePairs,
                searchHighlightId,
                focusedId,
                hoverTree,
                stableFocus,
                showAll,
            ),
        [
            layout,
            searchHighlightId,
            focusedId,
            hoverTree,
            stableFocus,
            showAll,
        ],
    );

    const [nodes, setNodes, onNodesChange] = useNodesState<Node<FeatureNodeData>>(
        flowElements.nodes,
    );
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge<FeatureEdgeData>>(
        flowElements.edges,
    );
    const [graphReady, setGraphReady] = useState(false);
    const initialFitDone = useRef(false);

    useEffect(() => {
        setNodes(flowElements.nodes);
        setEdges(flowElements.edges);
    }, [flowElements, setNodes, setEdges]);

    useEffect(() => {
        if (layout.visible.length === 0) {
            setGraphReady(true);
            return;
        }

        let cancelled = false;
        // Wait until RF has committed node measurements, then fit without animating
        // the first paint (avoids zoom-1 → fitView flicker).
        const id = requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                if (cancelled) return;
                const animate = initialFitDone.current;
                fitView({
                    padding: FIT_PADDING,
                    duration: animate ? 300 : 0,
                    minZoom: MIN_ZOOM,
                    maxZoom: MAX_ZOOM,
                });
                initialFitDone.current = true;
                setGraphReady(true);
            });
        });
        return () => {
            cancelled = true;
            cancelAnimationFrame(id);
        };
    }, [layout, focusedId, fitView]);

    useEffect(() => {
        return () => {
            if (infoCardTimer.current) clearTimeout(infoCardTimer.current);
            if (hoverLeaveTimer.current) clearTimeout(hoverLeaveTimer.current);
            if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
        };
    }, []);

    useEffect(() => {
        function onDocClick(e: MouseEvent) {
            if (!searchWrapRef.current?.contains(e.target as HTMLElement)) {
                setDropdownOpen(false);
            }
        }
        document.addEventListener('mousedown', onDocClick);
        return () => document.removeEventListener('mousedown', onDocClick);
    }, []);

    useEffect(() => {
        function onKeyDown(e: KeyboardEvent) {
            if (e.key !== 'Escape') return;
            if (search || dropdownOpen) return;
            if (focusedId) {
                e.stopPropagation();
                setFocusedId(null);
            }
        }
        document.addEventListener('keydown', onKeyDown);
        return () => document.removeEventListener('keydown', onKeyDown);
    }, [focusedId, search, dropdownOpen]);

    const searchPool = layout.visible;

    const matches = useMemo(
        () => (search.trim() ? searchFeatures(searchPool, search, 8) : []),
        [search, searchPool],
    );

    const zoomToFeature = useCallback(
        (id: string) => {
            if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
            setSearchHighlightId(id);
            setDropdownOpen(false);

            requestAnimationFrame(() => {
                fitView({
                    nodes: [{ id }],
                    duration: 450,
                    maxZoom: 1.4,
                    padding: 0.55,
                });
            });

            highlightTimeoutRef.current = setTimeout(() => setSearchHighlightId(null), 2500);
        },
        [fitView],
    );

    function clearSearch() {
        setSearch('');
        setSearchHighlightId(null);
        setDropdownOpen(false);
        if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
        fitView({
            padding: FIT_PADDING,
            duration: 400,
            minZoom: MIN_ZOOM,
            maxZoom: MAX_ZOOM,
        });
    }

    function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
        if (e.key === 'Enter' && matches.length > 0) {
            e.preventDefault();
            const first = matches[0];
            setSearch(first.name);
            zoomToFeature(first.id);
        } else if (e.key === 'Escape' && (search || dropdownOpen)) {
            e.stopPropagation();
            if (search) clearSearch();
            else setDropdownOpen(false);
        }
    }

    function handleNodeMouseEnter(e: React.MouseEvent, node: Node) {
        if (hoverLeaveTimer.current) clearTimeout(hoverLeaveTimer.current);
        setHoveredId(node.id);

        clearInfoCard();
        const feature = featureMap.get(node.id);
        if (!feature) return;

        const el = (e.target as HTMLElement).closest('.react-flow__node');
        const nodeRect = el?.getBoundingClientRect();
        infoCardTimer.current = setTimeout(() => {
            const nr = nodeRect ?? new DOMRect(e.clientX, e.clientY, 0, 0);
            const placed = placeInfoTooltip(nr, INFO_CARD_WIDTH, INFO_CARD_EST_H);
            setInfoCard({ feature, ...placed });
        }, INFO_CARD_DELAY_MS);
    }

    function handleNodeMouseLeave() {
        if (hoverLeaveTimer.current) clearTimeout(hoverLeaveTimer.current);
        hoverLeaveTimer.current = setTimeout(() => setHoveredId(null), 80);
        clearInfoCard();
    }

    return (
        <FeatureGraphSelectionContext.Provider value={selectionValue}>
            <div className="relative flex-1 min-h-0 h-full w-full bg-surface-1">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    nodeTypes={nodeTypes}
                    edgeTypes={edgeTypes}
                    nodesDraggable={false}
                    nodesConnectable={false}
                    elementsSelectable={false}
                    panOnDrag
                    panOnScroll={false}
                    zoomOnScroll
                    zoomOnPinch
                    preventScrolling
                    minZoom={MIN_ZOOM}
                    maxZoom={MAX_ZOOM}
                    proOptions={{ hideAttribution: true }}
                    className={clsx(
                        'features-flow !absolute inset-0 transition-opacity duration-150',
                        graphReady ? 'opacity-100' : 'opacity-0',
                    )}
                    onNodeMouseEnter={handleNodeMouseEnter}
                    onNodeMouseLeave={handleNodeMouseLeave}
                >
                    <Background
                        variant={BackgroundVariant.Dots}
                        gap={18}
                        size={1.2}
                        color="rgba(107, 114, 128, 0.35)"
                    />
                </ReactFlow>

                <div className="absolute top-3 left-3 z-10 flex flex-col gap-2 items-start">
                    {focusedId && (
                        <button
                            type="button"
                            onClick={showAll}
                            className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg border border-yellow-400/50 bg-surface-2 text-yellow-300 shadow-sm hover:bg-hover transition-colors"
                        >
                            <LayoutGrid className="w-3.5 h-3.5" />
                            Show all
                        </button>
                    )}
                    {!focusedId && (
                        <button
                            type="button"
                            onClick={() => setHideStandalone(v => !v)}
                            className={clsx(
                                'flex items-center gap-2 text-xs px-3 py-2 rounded-lg border transition-colors shadow-sm',
                                hideStandalone
                                    ? 'bg-surface-2 border-yellow-400/50 text-yellow-300'
                                    : 'bg-surface-2 border-surface-4 text-gray-400 hover:text-gray-200 hover:border-gray-500',
                            )}
                        >
                            {hideStandalone ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            {hideStandalone ? 'Show standalone features' : 'Hide standalone features'}
                        </button>
                    )}
                    <ZoomSlider />
                </div>

                <div ref={searchWrapRef} className="absolute top-3 right-3 z-10 w-64">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500 pointer-events-none" />
                        <input
                            className="input-base pl-8 pr-8 w-full text-sm py-2 shadow-sm bg-surface-2"
                            placeholder="Search & zoom…"
                            value={search}
                            onChange={e => {
                                setSearch(e.target.value);
                                setDropdownOpen(true);
                            }}
                            onFocus={() => setDropdownOpen(true)}
                            onKeyDown={handleSearchKeyDown}
                        />
                        {search && (
                            <button
                                type="button"
                                onClick={clearSearch}
                                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                                aria-label="Clear search"
                            >
                                <X className="w-3.5 h-3.5" />
                            </button>
                        )}
                    </div>
                    {dropdownOpen && matches.length > 0 && (
                        <ul className="mt-1 max-h-56 overflow-y-auto rounded-lg border border-surface-4 bg-surface-2 shadow-lg py-1">
                            {matches.map(f => (
                                <li key={f.id}>
                                    <button
                                        type="button"
                                        className="w-full text-left px-3 py-2 hover:bg-hover transition-colors"
                                        onClick={() => {
                                            setSearch(f.name);
                                            zoomToFeature(f.id);
                                        }}
                                    >
                                        <div className="text-sm text-gray-200 truncate">{f.name}</div>
                                        <div className="text-[10px] text-gray-500 truncate">
                                            {f.category.name}
                                        </div>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                    {dropdownOpen && search.trim() && matches.length === 0 && (
                        <div className="mt-1 rounded-lg border border-surface-4 bg-surface-2 px-3 py-2 text-xs text-gray-500 shadow-lg">
                            No features match
                        </div>
                    )}
                </div>

                {nodes.length === 0 && (
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <p className="text-sm text-gray-500">
                            {hideStandalone && !focusedId
                                ? 'No connected features — turn on “Show standalone features” to see all.'
                                : 'No features to display'}
                        </p>
                    </div>
                )}

                {infoCard && <FeatureInfoCard {...infoCard} />}
            </div>
        </FeatureGraphSelectionContext.Provider>
    );
}

export function FeaturesGraphView(props: FeaturesGraphViewProps) {
    return (
        <div className="flex-1 min-h-0 flex flex-col">
            <ReactFlowProvider>
                <FeaturesGraphCanvas {...props} />
            </ReactFlowProvider>
        </div>
    );
}
