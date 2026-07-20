# Section Engine v1

The Section Engine converts ordered, typed section specifications into deterministic Markdown.

Supported template tokens:

- `{{evidence:evidence.id}}` embeds a complete evidence payload.
- `{{evidence:evidence.id|field.path}}` embeds one field with stable numeric formatting.
- `{{table:table.id}}` embeds a rendered Markdown table.
- `{{figure:figure.id}}` embeds the generated PNG and its caption.

Each section specification declares an ID, title, order, heading level, and plugin-relative template path. The engine validates paths, renders sections, emits `section_catalog.json`, and assembles `manuscript.md` in deterministic order.
