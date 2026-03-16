# AI Change Checklist

Use this before considering an AI-assisted change complete.

1. Inspect the touched modules before editing.
2. Name the contract surfaces that change: understanding, action payloads, WebSocket messages, or UI rendering.
3. Keep the change vertical and local; avoid opportunistic refactors.
4. Add or update a regression test for every bug fixed or seam touched.
5. Run `./scripts/verify.sh`.
6. Update [PROJECT.md](../PROJECT.md) only if the contract or behavior changed.
