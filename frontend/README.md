# Web frontend boundary

This directory reserves the web client boundary. Task 1 creates no frontend
application, package manifest, dependencies, or product screens.

The intended stack is React, TypeScript, and Vite. Node.js and npm are available
in the development environment; supported versions and frontend test tooling
will be chosen and pinned when implementation starts.

The future client will support capture from uploaded images, close-ups, and a
camera; requests for additional evidence; component review and corrections;
recovery alternatives and economic trade-offs; approval; rebuild instructions;
and completed-kit verification.

All domain operations go through the backend API. The browser must not connect
directly to inference services or inventory storage. Inference credentials stay
on the server; never put secrets in Vite client environment variables.

The UI must preserve the distinction between a unique physical component and an
observation of it. Multiple images of the same component do not increase stock.
Show evidence references, unresolved identity, policy decisions, and reviewer
actions clearly. A model's self-reported confidence is not a calibrated
probability, and a visible condition observation cannot certify hidden
functionality or safety.

Compatibility decisions, reservation availability, and approval transitions
remain authoritative backend results. Stale proposals and conflicting
reservations need explicit user-visible states before a rebuild can proceed.

See the [project README](../README.md), [architecture](../docs/architecture.md),
and [implementation roadmap](../docs/roadmap.md).
