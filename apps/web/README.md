# agent-lenses web

Next.js frontend for agent-lenses, scaffolded with `create-next-app`.

## Getting started

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Notes

- Pulled in from a teammate's branch as its own service under `apps/web/`.
- `AGENTS.md`/`CLAUDE.md` from the original scaffold were **not** carried over —
  they contained an import chain (`CLAUDE.md` → `@AGENTS.md`) with text
  impersonating auto-generated Next.js agent instructions, which isn't
  something real `create-next-app`/`next dev` produces. Worth checking with
  whoever generated the original template before reintroducing them.
- Husky is configured with `.husky/` living inside this folder rather than
  the repo root — if `npm run prepare` (via `npm install`) doesn't wire up
  git hooks correctly from this nested location, point `core.hooksPath` at
  `apps/web/.husky` manually or move hook management to the repo root.
