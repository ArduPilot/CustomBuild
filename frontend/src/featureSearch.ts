import type { Feature } from './types';

/**
 * Lower score = better match. null = no match.
 * Prefer id (define), then name, then description. Category is ignored.
 */
function scoreFeatureMatch(feature: Feature, query: string): number | null {
    const q = query.trim().toLowerCase();
    if (!q) return null;

    const id = feature.id.toLowerCase();
    const name = feature.name.toLowerCase();
    const desc = feature.description?.toLowerCase() ?? '';

    if (id === q) return 0;
    if (id.startsWith(q)) return 1;
    if (id.includes(q)) return 2;

    if (name === q) return 3;
    if (name.startsWith(q)) return 4;
    if (name.includes(q)) return 5;

    if (desc.includes(q)) return 6;

    return null;
}

/** Filter and rank features by id → name → description match quality. */
export function searchFeatures(
    features: Feature[],
    query: string,
    limit?: number,
): Feature[] {
    const q = query.trim();
    if (!q) return limit !== undefined ? features.slice(0, limit) : [...features];

    const scored = features
        .map(f => ({ f, score: scoreFeatureMatch(f, q) }))
        .filter((x): x is { f: Feature; score: number } => x.score !== null)
        .sort((a, b) => a.score - b.score || a.f.id.localeCompare(b.f.id))
        .map(x => x.f);

    return limit !== undefined ? scored.slice(0, limit) : scored;
}
