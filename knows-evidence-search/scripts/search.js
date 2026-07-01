#!/usr/bin/env node
import { SOURCES, DEFAULT_BASE_URL, baseUrlEnv, fail, hasFlag, isEvidenceSource, optionalEnv, postJson, readOption, sourceNames } from "./common.js";
function usage() {
    return [
        "Usage:",
        "  node scripts/search.js --source <source> --query <query>",
        "",
        "Sources:",
        `  ${sourceNames().join(", ")}`,
        "",
        "Environment:",
        `  KNOWS_BASE_URL=<optional API root, defaults to ${DEFAULT_BASE_URL}>`,
        "  KNOWS_API_KEY=<optional bearer token for higher limits>"
    ].join("\n");
}
async function main() {
    const argv = process.argv.slice(2);
    if (hasFlag(argv, "--help") || hasFlag(argv, "-h")) {
        console.log(usage());
        return;
    }
    const source = readOption(argv, "--source");
    const query = readOption(argv, "--query");
    if (!isEvidenceSource(source)) {
        throw new Error(`Invalid or missing --source. Expected one of: ${sourceNames().join(", ")}`);
    }
    if (!query) {
        throw new Error("Missing --query.");
    }
    const baseUrl = baseUrlEnv("KNOWS_BASE_URL");
    const apiKey = optionalEnv("KNOWS_API_KEY");
    const result = await postJson(baseUrl, SOURCES[source].endpoint, apiKey, { query });
    console.log(JSON.stringify(result, null, 2));
}
main().catch(fail);
