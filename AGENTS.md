<INSTRUCTIONS>
## UI/UX Guardrails (No Ugly)
- Never introduce `alert()` or modal browser dialogs. Use inline UI feedback instead.
- Prefer subtle, styled status areas near the relevant controls (e.g., under the Join button).
- Errors should auto-heal when possible; avoid blocking flows unless required for correctness.
- When a dependency is missing (e.g., host token), show a non-blocking status and retry automatically.

## Socket/Session Behavior
- Client should remain resilient: auto-recover on reconnect and token changes without user prompts.
- If a host token is missing or stale, keep listening; don’t show blocking errors.

## Visual Consistency
- Favor the existing retro arcade aesthetic: neon glow, rounded cards, bold headers, and the Bungee font.
- Avoid harsh plain white blocks; use translucency or themed cards.
</INSTRUCTIONS>
