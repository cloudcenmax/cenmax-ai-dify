# Cenmax AI for Dify

A model-provider plugin for **self-hosted Dify** that uses Cenmax AI subscription OAuth. It exposes only public models available to the approved account and implements Chat Completions, streaming, image input when supported, and function tools.

## Status and authentication design

Dify's model-provider credential form does not supply this package's device authorization flow. This integration therefore uses a helper on the plugin-daemon host. The helper performs browser approval and stores rotating OAuth credentials privately. Dify stores an opaque random connection reference, never a pasted access or refresh token.

This initial package does **not** support Dify Cloud, automatic marketplace installation without host setup, or mutually untrusted tenants sharing an operating-system identity. The official Dify plugin daemon has been qualified with live sign-in, streaming tool calls and follow-up responses; a full Dify web application workflow has not been tested. See [qualification](QUALIFICATION.md). Marketplace acceptance is not claimed.

The public client `cenmax-dify` uses device-code and refresh-token grants with scope `chat`. The package contains no client secret and does not register itself.

## Host setup

Requires Linux/POSIX, Python 3.12, and Dify Plugin SDK 0.11.1. Mount a private persistent directory at `~/.config/cenmax-dify` for the operating-system user running the plugin daemon, and run the helper as that same user. Its owner must be that user, permissions 0700. In an image whose runtime user's home is `/home/dify`, the mount target is `/home/dify/.config/cenmax-dify`; verify your deployment's actual home first.

Dify daemon 0.6.15 filters the environment inherited by plugins. Setting `CENMAX_DIFY_CREDENTIAL_DIR` on the daemon alone does **not** pass it to the plugin. Use the default home directory mount. A custom absolute path is supported only when your operator has explicitly arranged and verified that the helper and actual plugin subprocess receive the same setting. Do not place credential files inside the plugin package or its extracted working directory.

Run from this package directory as the daemon user:

```sh
python3 -m cenmax.cli login
```

Open the displayed Cenmax AI link, confirm the code and select the account whose allowance should be used. The helper prints a random 256-bit **connection reference**. Keep it private and enter it in the Cenmax AI model credential field in Dify. It is a local capability, not a model ID or account name. No OAuth tokens are copied through Dify's UI.

```sh
python3 -m cenmax.cli models CONNECTION_REFERENCE
python3 -m cenmax.cli logout CONNECTION_REFERENCE
```

Use the model command to find entitled public IDs such as `pro` or `worker`. Add only a returned ID as a custom Cenmax AI model in Dify. Validation, model schema lookup and inference check the account catalogue; capabilities and limits are taken from that catalogue. No global fallback model list is bundled.

Package this directory using the [Dify plugin CLI](https://docs.dify.ai/en/develop-plugin/publishing/marketplace-listing/submit-plugin-to-marketplace), then install the resulting package in your self-hosted Dify deployment. Inspect the archive and run Dify's own validation before distributing it. `_assets/icon.svg`, the provider/model source, `manifest.yaml`, `main.py`, `requirements.txt`, and the `cenmax` module are required runtime files. Credentials must stay outside the package directory.

## Security and limits

- All network traffic goes to the fixed public HTTPS origin `https://console.ai.cenmax.in`; redirects and ambient proxies are refused. Model traffic uses `/app/v1`.
- Credential files use atomic writes, mode 0600, owner/link checks, and cross-process locks. An uncertain rotating refresh removes the local session and requires reconnect, preventing spent-token replay.
- Each authorization gets an unguessable reference. Do not reuse references across workspaces unless sharing that account allowance is intentional. Use Dify's credential controls and separate OS users/data volumes for mutually untrusted tenants. Plugins are not an OS isolation boundary.
- No history, file-management, workspace or tool-execution scopes are requested. Dify separately controls the tools it gives to a model.
- No telemetry is added. Errors are neutral and do not print raw service bodies. Generated response metadata contains only the selected public model identity; private fingerprints are not forwarded.
- Reported token counts come from the response. Preflight token estimates use a conservative UTF-8 byte count plus message overhead, not an exact model tokenizer. Monetary usage fields are zero because this integration consumes subscription allowance; zero does not imply unlimited use.

## Tests

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The standard-library tests cover the connection store, refresh serialization/failure recovery, catalogue boundary, and SSE framing. Dependency installation belongs in the isolated plugin runtime, not global Python.

## Source, privacy and support

[Source and releases](https://github.com/cloudcenmax/cenmax-ai-dify) · [Report an issue](https://github.com/cloudcenmax/cenmax-ai-dify/issues) · [Privacy](PRIVACY.md). Support: support@cenmax.in. Do not include connection references, OAuth credentials, prompts, or private model responses in an issue. [Marketplace preparation](MARKETPLACE.md) records the remaining submission requirements and self-hosted limitation.
