# Marketplace preparation

The package provides subscription OAuth model access for self-hosted Dify through a host login helper. It does not provide Dify Cloud support or a native in-form OAuth login. This limitation must remain visible in any listing and reviewer notes.

Prepared assets include the English README, icon, MIT license, pinned SDK dependency, source repository link and manifest-linked privacy policy. Build a `.difypkg` with the official Dify CLI:

```sh
dify plugin package . -o cenmax_ai-0.1.0.difypkg
```

Inspect the archive before uploading: it must contain no credentials, connection references, environment files, caches, virtual environments, logs or test artifacts. `.difyignore` excludes these files. The official CLI packaging and plugin-daemon installation are covered by [qualification](QUALIFICATION.md).

The current official Marketplace toolkit validator, including online dependency vulnerability checks, passed the prepared archive; see [qualification](QUALIFICATION.md) for its revision and review warnings. Rerun it after changes. Before submitting, verify that the source repository and maintainer support channel are public, confirm the author identity in Creator Center, check name availability, provide screenshots from an actual supported installation and include the exact supported versions. Do not describe daemon qualification as a tested full Dify web workflow.

Use the higher applicable risk classification in the current submission form: the helper handles authentication credentials and private local files, and inference transmits user content to Cenmax AI. Document the fixed HTTPS destination, host credential mount, required operator setup and Cloud limitation. Do not claim signature verification or Marketplace approval for an unsigned local package.

No Marketplace submission, maintainer account registration or upstream pull request has been performed by preparing these files. Review can require changes before acceptance; an operator-only login helper may limit listing suitability.

Official requirements: [submission requirements](https://github.com/langgenius/dify-plugins/blob/main/docs/plugin-submission-requirements.md), [submission template](https://github.com/langgenius/dify-plugins/blob/main/.github/pull_request_template.md).
