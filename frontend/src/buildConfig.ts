import { load as yamlLoad } from 'js-yaml';
import Ajv, { type ValidateFunction } from 'ajv/dist/2020';

const CONFIG_VERSION = '0.0.1';

interface BuildConfigVehicle {
    id: string;
    name: string;
}

interface BuildConfigFirmwareVersion {
    id: string;
    name: string;
    type: string;
    remote_name: string;
}

interface BuildConfigBoard {
    id: string;
    name: string;
}

export interface BuildConfig {
    config_version: string;
    vehicle: BuildConfigVehicle;
    version?: BuildConfigFirmwareVersion;
    board?: BuildConfigBoard;
    selected_features: string[];
    /** When true the config loader applies board defaults instead of selected_features */
    use_default_features?: boolean;
}

/** Build a partial config from URL query parameters. Absent/empty params leave fields undefined. */
export function configFromQueryParams(params: URLSearchParams): BuildConfig | null {
    const vehicleId = params.get('vehicle_id');
    if (!vehicleId) return null;

    const versionId = params.get('version_id');
    const boardId = params.get('board_id');

    return {
        config_version: CONFIG_VERSION,
        vehicle: { id: vehicleId, name: vehicleId },
        version: versionId
            ? { id: versionId, name: versionId, type: 'tag', remote_name: '' }
            : undefined,
        board: boardId
            ? { id: boardId, name: boardId }
            : undefined,
        selected_features: [],
        use_default_features: true,
    };
}

const schemaCache = new Map<string, Record<string, unknown>>();
const validatorCache = new Map<string, ValidateFunction>();
const ajv = new Ajv({ allErrors: true });

async function fetchSchema(version: string): Promise<Record<string, unknown>> {
    const cached = schemaCache.get(version);
    if (cached) return cached;
    const res = await fetch(`/schemas/config/${version}.json`);
    if (!res.ok)
        throw new Error(`No schema found for config version "${version}". The config file may be too new or unsupported.`);
    const schema = await res.json() as Record<string, unknown>;
    schemaCache.set(version, schema);
    return schema;
}

async function getValidator(version: string): Promise<ValidateFunction> {
    const cached = validatorCache.get(version);
    if (cached) return cached;
    const schema = await fetchSchema(version);
    const validate = ajv.compile(schema);
    validatorCache.set(version, validate);
    return validate;
}

async function validateConfig(raw: unknown): Promise<BuildConfig> {
    if (typeof raw !== 'object' || raw === null)
        throw new Error('Config must be a YAML object');

    const obj = raw as Record<string, unknown>;
    if (typeof obj.config_version !== 'string' || !obj.config_version.match(/^\d+\.\d+\.\d+$/))
        throw new Error('Invalid or missing "config_version" field (expected semver, e.g. "0.0.1")');

    const validate = await getValidator(obj.config_version);

    if (!validate(raw)) {
        const messages = (validate.errors ?? [])
            .map(e => `  - ${e.instancePath || '(root)'} ${e.message}`)
            .join('\n');
        throw new Error(`Config validation failed:\n${messages}`);
    }

    return raw as BuildConfig;
}

export async function parseConfigYaml(yamlText: string): Promise<BuildConfig> {
    let raw: unknown;
    try {
        raw = yamlLoad(yamlText);
    } catch (e: unknown) {
        throw new Error(
            `YAML parse error: ${e instanceof Error ? e.message : String(e)}`
        );
    }
    return validateConfig(raw);
}
