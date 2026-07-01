#!/usr/bin/env node
import { RELEASES_MANIFEST_URL, SKILL_NAME, SKILL_VERSION, fail, readOption } from "./common.js";
function compareVersions(left, right) {
    const a = left.split(".").map((part) => Number(part));
    const b = right.split(".").map((part) => Number(part));
    for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
        const diff = (a[i] || 0) - (b[i] || 0);
        if (diff !== 0) {
            return diff;
        }
    }
    return 0;
}
async function main() {
    const manifestUrl = readOption(process.argv.slice(2), "--manifest-url") || RELEASES_MANIFEST_URL;
    const response = await fetch(manifestUrl);
    if (!response.ok) {
        throw new Error(`Failed to fetch release manifest: HTTP ${response.status} ${response.statusText}`);
    }
    const manifest = (await response.json());
    if (manifest.skill !== SKILL_NAME) {
        throw new Error(`Unexpected release manifest skill: ${manifest.skill}`);
    }
    const latest = manifest.releases.find((release) => release.version === manifest.latestVersion);
    const updateAvailable = compareVersions(manifest.latestVersion, SKILL_VERSION) > 0;
    console.log(JSON.stringify({
        skill: SKILL_NAME,
        currentVersion: SKILL_VERSION,
        latestVersion: manifest.latestVersion,
        updateAvailable,
        detailApiAvailable: manifest.detailApiAvailable,
        authentication: manifest.authentication,
        rateLimits: manifest.rateLimits,
        downloadUrl: latest?.downloadUrl,
        sha256: latest?.sha256,
        notes: latest?.notes || []
    }, null, 2));
}
main().catch(fail);
