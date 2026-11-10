# Contributing to rpt-mcp

Thank you for taking the time to contribute! This document covers everything you need to get started.

---

## Ways to contribute

- **Bug reports** — open an issue using the Bug Report template
- **Feature requests** — open an issue using the Feature Request template
- **Documentation improvements** — fix typos, improve examples, clarify parameters
- **Code contributions** — bug fixes, new tools, or improvements to existing ones

---

## Development setup

### Prerequisites

- Python 3.11 or later
- A SAP RPT Playground API token (get one at [https://rpt.cloud.sap/](https://rpt.cloud.sap/))

### Clone and install

```bash
git clone <repo-url>
cd rpt-mcp
pip install -r requirements.txt
```

### Configure your token

```bash
cp .env.example .env
# Edit .env and set RPT_API_TOKEN=<your-token>
```

### Run the server locally

```bash
# stdio mode (connect from Claude Code)
python3 server.py

# HTTP mode (connect from any MCP HTTP client)
python3 server.py --http
```

### Verify it works

Start the server and from your MCP client call:
```
test_connection()
```

You should see `HTTP 200 — OK ✓`.

---

## Submitting changes

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b fix/describe-your-change
   ```

2. **Make your changes.** Keep each pull request focused on a single concern.

3. **Test manually** — all three endpoints (predict, forecast, decisions) should return expected results after your change.

4. **Check syntax:**
   ```bash
   python3 -c "import ast; ast.parse(open('server.py').read()); print('OK')"
   ```

5. **Update documentation** — if you add or change a tool parameter, update the docstring in `server.py` and the corresponding section in `README.md`.

6. **Open a pull request** against `main`. Include:
   - A clear description of what changed and why.
   - The endpoint(s) affected.
   - How you tested it.

---

## Code style

- Follow the existing style in `server.py` — consistent indentation, type hints on all function signatures, and concise docstrings.
- Tool docstrings are user-facing: write them for the AI assistant that will read and act on them, not for Python developers.
- Do not add inline comments that restate what the code does. Only comment non-obvious intent.
- Keep each tool self-contained. Shared logic belongs in private helper functions prefixed with `_`.

---

## Reporting bugs

Please use the **Bug Report** issue template. Include:
- The tool you called and the parameters you passed (redact any API tokens).
- The full raw response string.
- The Python version and OS.

---

## Security

**Never include API tokens in issues, pull requests, or code.**

If you discover a security vulnerability in this project, please report it privately by opening a GitHub Security Advisory rather than a public issue.

---

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
