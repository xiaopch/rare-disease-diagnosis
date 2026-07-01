export const SKILL_NAME = "knows-evidence-search";
export const SKILL_VERSION = "1.0.0";
export const RELEASES_MANIFEST_URL = "https://developers.nullht.com/skills/releases.json";
export const DEFAULT_BASE_URL = "https://api.nullht.com/v1";
export const SOURCES = {
    paper_en: {
        label: "English paper evidences",
        endpoint: "/evidences/ai_search_paper_en"
    },
    paper_cn: {
        label: "Chinese paper evidences",
        endpoint: "/evidences/ai_search_paper_cn"
    },
    meeting: {
        label: "Meeting evidences",
        endpoint: "/evidences/ai_search_meeting"
    },
    guide: {
        label: "Guide evidences",
        endpoint: "/evidences/ai_search_guide"
    },
    trial: {
        label: "Trial evidences",
        endpoint: "/evidences/ai_search_trial"
    },
    package_insert: {
        label: "Package insert evidences",
        endpoint: "/evidences/ai_search_package_insert"
    }
};
export function sourceNames() {
    return Object.keys(SOURCES);
}
export function isEvidenceSource(value) {
    return Boolean(value && value in SOURCES);
}
export function baseUrlEnv(name) {
    return process.env[name] || DEFAULT_BASE_URL;
}
export function optionalEnv(name) {
    return process.env[name];
}
export function apiUrl(baseUrl, endpoint) {
    return `${baseUrl.replace(/\/+$/g, "")}${endpoint}`;
}
export async function postJson(baseUrl, endpoint, apiKey, payload) {
    const headers = {
        "Content-Type": "application/json"
    };
    if (apiKey) {
        headers.Authorization = `Bearer ${apiKey}`;
    }
    const response = await fetch(apiUrl(baseUrl, endpoint), {
        method: "POST",
        headers,
        body: JSON.stringify(payload)
    });
    const text = await response.text();
    const parsed = parseJson(text);
    if (!response.ok) {
        const body = parsed === undefined ? text : JSON.stringify(parsed);
        throw new Error(`KnowS API request failed: HTTP ${response.status} ${response.statusText}. ${body}`);
    }
    return parsed;
}
export function parseJson(text) {
    if (!text.trim()) {
        return undefined;
    }
    try {
        return JSON.parse(text);
    }
    catch {
        return text;
    }
}
export function readOption(argv, name) {
    const index = argv.indexOf(name);
    if (index === -1) {
        return undefined;
    }
    return argv[index + 1];
}
export function hasFlag(argv, name) {
    return argv.includes(name);
}
export function fail(error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(message);
    process.exitCode = 1;
}
