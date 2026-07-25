import type { Feature } from './types';

interface FeatureMaps {
    featureMap: Map<string, Feature>;
    forwardDeps: Map<string, Set<string>>;
    reverseDeps: Map<string, Set<string>>;
}

export function buildFeatureMaps(features: Feature[]): FeatureMaps {
    const featureMap = new Map<string, Feature>();
    const forwardDeps = new Map<string, Set<string>>();
    const reverseDeps = new Map<string, Set<string>>();

    for (const f of features) {
        featureMap.set(f.id, f);
        forwardDeps.set(f.id, new Set(f.dependencies));
        for (const depId of f.dependencies) {
            if (!reverseDeps.has(depId)) reverseDeps.set(depId, new Set());
            reverseDeps.get(depId)!.add(f.id);
        }
    }

    return { featureMap, forwardDeps, reverseDeps };
}

/** Transitive dependencies of `id`, limited to IDs present in `featureMap`. */
export function collectTransitiveDeps(
    id: string,
    forwardDeps: Map<string, Set<string>>,
    featureMap: Map<string, Feature>,
): Set<string> {
    const visited = new Set<string>();
    const stack = [...(forwardDeps.get(id) ?? [])];
    while (stack.length) {
        const cur = stack.pop()!;
        if (visited.has(cur) || !featureMap.has(cur)) continue;
        visited.add(cur);
        forwardDeps.get(cur)?.forEach(d => stack.push(d));
    }
    return visited;
}

/** Transitive dependents of `id` (features that need it, directly or indirectly). */
export function collectTransitiveDependents(
    id: string,
    reverseDeps: Map<string, Set<string>>,
): Set<string> {
    const visited = new Set<string>();
    const stack = [...(reverseDeps.get(id) ?? [])];
    while (stack.length) {
        const cur = stack.pop()!;
        if (visited.has(cur)) continue;
        visited.add(cur);
        reverseDeps.get(cur)?.forEach(d => stack.push(d));
    }
    return visited;
}

/** Descendants of `start` within `ids` (excludes `start`). */
function reachableWithin(
    start: string,
    ids: Set<string>,
    forwardDeps: Map<string, Set<string>>,
): Set<string> {
    const visited = new Set<string>();
    const stack = [...(forwardDeps.get(start) ?? [])];
    while (stack.length) {
        const cur = stack.pop()!;
        if (visited.has(cur) || !ids.has(cur)) continue;
        visited.add(cur);
        forwardDeps.get(cur)?.forEach(d => stack.push(d));
    }
    return visited;
}

/**
 * Covering dependency edges only (transitive reduction).
 */
export function reducedDependencyEdges(
    ids: Set<string>,
    forwardDeps: Map<string, Set<string>>,
): Array<{ source: string; target: string }> {
    const edges: Array<{ source: string; target: string }> = [];

    for (const id of ids) {
        const directs = [...(forwardDeps.get(id) ?? [])]
            .filter(d => ids.has(d))
            .sort((a, b) => a.localeCompare(b));

        for (const dep of directs) {
            const redundant = directs.some(other => {
                if (other === dep) return false;
                return reachableWithin(other, ids, forwardDeps).has(dep);
            });
            if (!redundant) edges.push({ source: id, target: dep });
        }
    }

    return edges;
}

/**
 * Best-effort expand: keep seeds that exist in the catalog and add transitive
 * deps that exist. Missing dep IDs are skipped; parents are kept.
 */
function expandSelection(
    seedIds: Iterable<string>,
    featureMap: Map<string, Feature>,
    forwardDeps: Map<string, Set<string>>,
): Set<string> {
    const resolved = new Set<string>();
    for (const id of seedIds) {
        if (!featureMap.has(id)) continue;
        resolved.add(id);
        for (const dep of collectTransitiveDeps(id, forwardDeps, featureMap)) {
            resolved.add(dep);
        }
    }
    return resolved;
}

/** Board/firmware defaults with available transitive dependencies filled in. */
export function resolveDefaultSelection(features: Feature[]): Set<string> {
    const { featureMap, forwardDeps } = buildFeatureMaps(features);
    return expandSelection(
        features.filter(f => f.default.enabled).map(f => f.id),
        featureMap,
        forwardDeps,
    );
}

interface ApplyFeatureSelectionResult {
    selected: Set<string>;
    /** Requested IDs not present in the feature catalog at all. */
    missing: string[];
    /** IDs auto-added to satisfy dependencies (not in the original request). */
    autoAdded: string[];
}

/**
 * Resolve a requested feature set against the catalog (best-effort): keep
 * existing IDs, auto-add available deps, skip missing dep IDs.
 */
export function applyFeatureSelection(
    requestedIds: string[],
    features: Feature[],
): ApplyFeatureSelectionResult {
    const { featureMap, forwardDeps } = buildFeatureMaps(features);
    const requested = new Set(requestedIds);

    const missing = requestedIds.filter(id => !featureMap.has(id));
    const selected = expandSelection(requestedIds, featureMap, forwardDeps);
    const autoAdded = [...selected].filter(id => !requested.has(id));

    return { selected, missing, autoAdded };
}
