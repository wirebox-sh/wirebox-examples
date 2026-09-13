# Wirebox Examples

Official examples and recipes for building autonomous AI agents with [Wirebox](https://wirebox.sh).

## Examples

- [**browser-use**](./browser-use): Autonomous web signup (Notion) and email verification (OTP & magic links) with [Browser Use](https://browser-use.com).

## Quickstart (`browser-use`)

The [`browser-use`](./browser-use) example demonstrates an autonomous browser agent that registers on web services (e.g. Notion) by reading its own Wirebox email inbox to handle OTP codes and magic links.

```bash
git clone https://github.com/wirebox-sh/wirebox-examples.git
cd wirebox-examples/browser-use

# Copy and configure environment variables
cp .env.example .env

# Run autonomous agent with live Chromium window
uv run wirebox-browser-use "Go to notion.com, sign in with my email, wait for the verification code, and log in"
```

## Documentation

- **Website**: [https://wirebox.sh](https://wirebox.sh)
- **Documentation**: [https://docs.wirebox.sh](https://docs.wirebox.sh)
- **Console**: [https://wirebox.sh/console](https://wirebox.sh/console)

## License

[MIT](./LICENSE) © [Wirebox](https://wirebox.sh)
