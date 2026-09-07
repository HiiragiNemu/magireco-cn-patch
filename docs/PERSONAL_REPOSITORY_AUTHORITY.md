# Personal repository authority

Primary: `HiiragiNemu/magireco-cn-patch`, branch `main`.
Secondary mirror: `MagirecoCN-Revival-Project/magireco-cn-patch`, branch `main`.

All new development, release assets, build configuration and versions originate in
the personal repository. Do not develop in or import automatically from the
organization mirror. Normal mirroring is personal → organization, fast-forward
only. Independent organization commits stop the mirror for explicit reconciliation.
An unavailable mirror never blocks the personal build or release.

The source mirror runs on main pushes and after the personal release workflow.
It uses the existing `GH_TOKEN` secret, scoped for the two repositories. Tokens
are not written into files. There is no scheduled polling or automatic visibility
change. The organization copy skips producer and mirror jobs.

Initial reconciliation retains personal game resources and current runtime fixes.
The ten independently present `tools/story-import` files were preserved from
organization commit `843214b87eeb57835ce5dc3863f8f68502cb07c0`; their 24 tests pass.
No converted game story is installed merely by adding these tools.

Rejected inputs: organization scenario Base64 strings containing `object-storage`
(88 fields in 60 files), shortened download domains, obsolete runtime dictionaries,
and repository-local guard/policy installation. The personal versions are retained.
Both historical organization heads are preserved as merge parents for traceability.
One isolated wording difference is retained in the reconciliation evidence, not
treated as a verified translation change.

Large existing game-resource archives remain in GitHub Releases. Do not bulk-copy
them into the source repository. This migration does not alter `image_native` or
generate Memoria images. GitHub release assets remain authoritative in the personal
repository; no duplicate multi-gigabyte organization release upload is performed.
