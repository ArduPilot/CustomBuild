export interface Vehicle {
    id: string;
    name: string;
}

interface RemoteInfo {
    name: string;
    url: string;
}

export interface Version {
    id: string;
    name: string;
    type: 'beta' | 'stable' | 'latest' | 'tag';
    remote: RemoteInfo;
    commit_ref?: string;
    vehicle_id: string;
    fw_server_path?: string;
}

export interface Board {
    id: string;
    name: string;
    vehicle_id: string;
    version_id: string;
    fw_server_path?: string;
}

interface Category {
    id: string;
    name: string;
    description?: string;
}

interface FeatureDefault {
    enabled: boolean;
    source: 'firmware-server' | 'build-options-py';
}

export interface Feature {
    id: string;
    name: string;
    category: Category;
    description?: string;
    vehicle_id: string;
    version_id: string;
    board_id: string;
    default: FeatureDefault;
    dependencies: string[];
}

export type BuildState = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILURE' | 'ERROR' | 'TIMED_OUT';

interface BuildProgress {
    percent: number;
    state: BuildState;
}

interface BuildVersionInfo {
    id: string;
    name?: string;
    type?: 'beta' | 'stable' | 'latest' | 'tag';
    remote_info: RemoteInfo;
    git_hash: string;
}

export interface Build {
    build_id: string;
    vehicle: Vehicle;
    board: Board;
    version: BuildVersionInfo;
    selected_features: string[];
    progress: BuildProgress;
    time_created: number;
}

export interface BuildSubmitResponse {
    build_id: string;
    url: string;
    status: 'submitted';
}

export interface BuildRequest {
    vehicle_id: string;
    board_id: string;
    version_id: string;
    selected_features: string[];
}

export interface StandardArtifact {
    name: string;
    url: string;
    format: string;
    size?: number;
}

export type FormStep =
    | 'vehicle'
    | 'version'
    | 'board'
    | 'choice'
    | 'standard-files'
    | 'features'
    | 'building'
    | 'done';
