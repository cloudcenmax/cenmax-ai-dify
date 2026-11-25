# Qualification

Tested on 25 November 2026 with Python 3.12.3, Dify Plugin SDK 0.11.1 and the official Dify plugin daemon/CLI 0.6.15 on Linux ARM64. The unchanged daemon binaries came from the official `langgenius/dify-plugin-daemon:0.6.15-local` ARM64 image, manifest digest `sha256:f825dd420563d30b647bb1b2f3b216a2066aa851dc2128103bd7938d50169370`. The daemon reported commit `14d714820d475075e15bd8dae605d61298382213`.

The binaries ran on a minimal Ubuntu 24.04 runtime with PostgreSQL 16 and Redis 7. This was a real local plugin daemon and SDK subprocess, not a simulated adapter context. A full Dify API/web deployment and Dify Cloud were not tested; no compatibility claim is made for those workflows or other daemon/SDK versions.

Confirmed:

- Official CLI packaging, package upload, manifest parsing and daemon installation.
- Live device authorization with scope `chat`, entitled public model discovery and custom model schema lookup.
- Actual daemon credential validation and model invocation through the installed SDK subprocess.
- Streamed `Worker by Cenmax AI` function call, local execution of a marker tool, and streamed follow-up containing the exact generated marker.
- Real access/refresh-token rotation after advancing only the private local expiration timestamp.
- Nonstreaming model invocation and SDK result serialization.
- Logout revocation, local session deletion, HTTP 401 for the former access token, and rejection of the removed connection by the daemon.

Nine standard-library security tests passed. The official Marketplace toolkit at commit `83ee707c1dde758678f94a311f15b42d74f8c402` reported zero blocking failures and zero check-execution failures. Its online OSV check found no known vulnerabilities in the package's pinned dependency set; this is not a guarantee about every transitive dependency or future advisory.

Review warnings remain for the unspecified minimum Dify web version, heuristic credential-return matches, and URLs assembled from the fixed public origin. The credential-return matches describe internal OAuth token exchange and public model schema creation, not tokens returned to the model consumer. The package contains no credentials. PR context, duplicate Marketplace versions and reviewer acceptance require separate checks.

The host setup uses the daemon user's default `~/.config/cenmax-dify` directory. Daemon 0.6.15 filters arbitrary inherited environment variables; setting a custom path on the daemon alone is insufficient. No plugin credentials belong in a source archive or release package.

The package is unsigned for local installation. Official Marketplace acceptance and a tested full Dify web workflow remain separate release gates. See [Marketplace preparation](MARKETPLACE.md).
