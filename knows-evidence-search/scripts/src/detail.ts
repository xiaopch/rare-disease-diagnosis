#!/usr/bin/env node
import { RELEASES_MANIFEST_URL, SKILL_VERSION } from "./common.js";

declare const process: {
  exitCode?: number;
};

console.error(
  [
    `Evidence detail lookup is not available in knows-evidence-search v${SKILL_VERSION}.`,
    "The public OpenAPI contract does not expose evidence detail endpoints yet.",
    `Check ${RELEASES_MANIFEST_URL} for detailApiAvailable before upgrading or retrying.`
  ].join("\n")
);
process.exitCode = 2;
