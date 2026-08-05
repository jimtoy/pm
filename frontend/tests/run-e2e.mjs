// Playwright's reuseExistingServer:false check probes the webServer URL
// *before* running globalSetup and before spawning the webServer command, so
// a stale container left over from an interrupted previous run (or from
// `scripts/start.sh`) makes Playwright fail immediately rather than replacing
// it. Clearing any existing container as a separate step first, before
// Playwright starts at all, sidesteps that ordering issue. This runs via
// Node (not a shell script) so it behaves the same on Mac, Linux, and PC.
import { execFileSync, spawnSync } from "node:child_process";

execFileSync(
  "docker",
  ["compose", "-f", "docker-compose.yml", "-f", "docker-compose.e2e.yml", "down", "-v"],
  { cwd: "..", stdio: "inherit" }
);

const result = spawnSync("npx", ["playwright", "test", ...process.argv.slice(2)], {
  stdio: "inherit",
  shell: true,
});

process.exit(result.status ?? 1);
