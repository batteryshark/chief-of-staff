# Dependency notices

The source checkout includes dependency declarations and a lockfile, not installed npm packages. The versions and SPDX licenses below are recorded in `package-lock.json`.

| Packages | Version | License |
|---|---|---|
| zod (runtime) | 4.1.8 | MIT |
| esbuild; optional `@esbuild/*` platform packages | 0.25.12 | MIT |
| @opencode/client, @opencode/protocol, @opencode/schema | 2.0.23 | MIT |
| @standard-schema/spec | 1.1.0 | MIT |
| effect | 4.0.0-rc.112 | MIT |
| fast-check | 4.10.2 | MIT |
| pure-rand | 8.4.2 | MIT |
| msgpackr | 2.1.0 | MIT |
| msgpackr-extract; optional `@msgpackr-extract/*` platform packages | 3.0.4 | MIT |
| node-gyp-build-optional-packages | 5.2.2 | MIT |
| detect-libc | 2.1.2 | Apache-2.0 |

Zod is the runtime dependency bundled by `scripts/build.mjs`. The build copies its complete installed LICENSE into `dist/THIRD_PARTY_NOTICES.md`. Keep that notice with a redistributed bundle. esbuild and the OpenCode client are development dependencies; their transitive dependencies include the packages above. Preserve each package's supplied license and notices when distributing installed dependencies. detect-libc's Apache-2.0 license applies independently of this repository's MIT grant.

The lockfile records exact package tarball URLs and integrity pins. The installed package's LICENSE/NOTICE files are the authority for its full notice text; this table doesn't replace those files. Direct package references: [Zod 4.1.8](https://www.npmjs.com/package/zod/v/4.1.8), [esbuild 0.25.12](https://www.npmjs.com/package/esbuild/v/0.25.12), [OpenCode client 2.0.23](https://www.npmjs.com/package/@opencode/client/v/2.0.23).

Host applications, models, a2a and optional services are supplied separately and keep their own terms.
