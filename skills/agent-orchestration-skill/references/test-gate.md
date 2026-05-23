# Verification Gate

## XS/S

Run the smallest meaningful validation: targeted unit test, typecheck for touched module, lint for changed files, or a focused manual/browser check.

## M

Run targeted tests plus the relevant project-level gate: lint, typecheck, build, or integration tests.

## L/XL

Run the full available matrix. If UI behavior changed, include browser QA. If auth/payment/data/security changed, include high-effort review.

## Docker

Rebuild Docker after dependency, container, runtime, environment, server startup, or deployment-affecting changes. Do not rebuild after a tiny isolated source edit unless the app must be exercised inside the container.
