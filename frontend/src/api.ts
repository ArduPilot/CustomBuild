import type {
    Vehicle, Version, Board, Feature, Build,
    BuildRequest, BuildSubmitResponse, StandardArtifact,
} from './types';
import { parseConfigYaml, type BuildConfig } from './buildConfig';

const API_BASE = '/api/v1';

function apiUrl(...segments: string[]): string {
    const path = segments.map(encodeURIComponent).join('/');
    return `${API_BASE}/${path}`;
}

export function buildArtifactUrl(buildId: string): string {
    return apiUrl('builds', buildId, 'artifact');
}

function buildConfigUrl(buildId: string): string {
    return apiUrl('builds', buildId, 'config');
}

export async function fetchBuildConfig(buildId: string): Promise<BuildConfig> {
    const res = await fetch(buildConfigUrl(buildId));
    if (!res.ok) throw new Error(`Config unavailable (${res.status})`);
    return parseConfigYaml(await res.text());
}

export function commitUrl(remoteUrl: string, gitHash: string): string {
    return `${remoteUrl.replace(/\.git$/, '')}/commit/${gitHash}`;
}

async function apiFetch<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
    return res.json() as Promise<T>;
}

export async function fetchVehicles(): Promise<Vehicle[]> {
    return apiFetch<Vehicle[]>(apiUrl('vehicles'));
}

export async function fetchVersions(vehicleId: string): Promise<Version[]> {
    return apiFetch<Version[]>(apiUrl('vehicles', vehicleId, 'versions'));
}

export async function fetchBoards(vehicleId: string, versionId: string): Promise<Board[]> {
    return apiFetch<Board[]>(apiUrl('vehicles', vehicleId, 'versions', versionId, 'boards'));
}

export async function fetchFeatures(vehicleId: string, versionId: string, boardId: string): Promise<Feature[]> {
    return apiFetch<Feature[]>(
        apiUrl('vehicles', vehicleId, 'versions', versionId, 'boards', boardId, 'features'),
    );
}

export async function fetchBuilds(limit = 10, offset = 0): Promise<Build[]> {
    return apiFetch<Build[]>(`${apiUrl('builds')}?limit=${limit}&offset=${offset}`);
}

export async function fetchBuild(buildId: string): Promise<Build> {
    return apiFetch<Build>(apiUrl('builds', buildId));
}

export async function submitBuild(req: BuildRequest): Promise<BuildSubmitResponse> {
    const res = await fetch(apiUrl('builds'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`Submit error ${res.status}: ${await res.text()}`);
    return res.json() as Promise<BuildSubmitResponse>;
}

export async function fetchBuildLogs(buildId: string): Promise<string> {
    const res = await fetch(apiUrl('builds', buildId, 'logs'));
    if (!res.ok) throw new Error('Logs unavailable');
    return res.text();
}

export async function fetchStandardArtifacts(
    vehicleId: string,
    versionId: string,
    boardId: string,
): Promise<StandardArtifact[] | null> {
    const res = await fetch(
        apiUrl('vehicles', vehicleId, 'versions', versionId, 'boards', boardId, 'standard_artifacts'),
    );
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
    return res.json() as Promise<StandardArtifact[]>;
}
