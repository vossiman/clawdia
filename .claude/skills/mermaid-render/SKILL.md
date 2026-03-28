---
name: mermaid-render
description: Render mermaid diagrams to PNG. Use whenever you need to create or render a .mmd file to an image, generate architecture diagrams, flowcharts, or any visual diagram output.
allowed-tools:
  - Bash
  - Write
  - Read
---

Render mermaid diagram files to PNG using the globally installed `mmdc` CLI.

## Steps

1. Write the `.mmd` file to `/tmp/` (or the target location)
2. Ensure the puppeteer config exists:
   ```bash
   test -f /tmp/puppeteer-config.json || echo '{"args": ["--no-sandbox"]}' > /tmp/puppeteer-config.json
   ```
3. Render:
   ```bash
   mmdc -i /path/to/diagram.mmd -o /path/to/output.png -t dark -b transparent -w 1200 -p /tmp/puppeteer-config.json
   ```

## If Chrome headless is missing

If you get a "Could not find Chrome" error, install it:
```bash
cd /home/vossi/.npm-global/lib/node_modules/@mermaid-js/mermaid-cli && npx puppeteer browsers install chrome-headless-shell
```
Then retry the render command.

## Notes

- `mmdc` is at `/home/vossi/.npm-global/bin/mmdc`
- The `--no-sandbox` flag is required due to AppArmor restrictions on Ubuntu 23.10+
- Supported output formats: png, svg, pdf (change the file extension)
