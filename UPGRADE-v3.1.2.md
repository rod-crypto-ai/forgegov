# ForgeGov v3.1.2 upgrade baseline

This release is designed to overlay the fully validated ForgeGov v3.1.1 repository after the v3.1.1 verification/dependency-security corrections.

## Secure frontend lockfile

The release package intentionally does not replace `frontend/package-lock.json`. The validated v3.1.1 repository already contains the corrected secure dependency lock (including Next.js 16.3.1 and the associated audited transitive dependency updates). The v3.1.2 install procedure preserves that lockfile and updates only its root package version metadata from 3.1.1 to 3.1.2 before running `npm ci` through the release verifier.

Do not install v3.1.2 over an older uncorrected v3.1.1 checkout. The v3.1.2 verifier checks that the preserved lockfile still pins Next.js 16.3.1 and stops before runtime validation if the secure baseline is missing.

## Release rule

Run `./VERIFY_V3.1.2.command` successfully through all 19 stages, including `/api/health/` and `/api/ready/`, before any commit, push, or tag.
