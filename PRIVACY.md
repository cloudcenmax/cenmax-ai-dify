# Privacy

This plugin connects a self-hosted Dify installation to Cenmax AI. It sends model catalogue requests and the prompts, conversation context, image input, tool definitions and tool results supplied by Dify to `https://console.ai.cenmax.in` over HTTPS. It does not request Cenmax AI history, memory, files, or workspace permissions. Tool execution belongs to Dify; this model plugin does not execute tools.

The host login helper requests the OAuth `chat` scope. It stores access and rotating refresh tokens in private local files under the daemon user's `~/.config/cenmax-dify`, with owner checks and restrictive permissions. These files are not encrypted by this plugin; protect the host and backups. Dify stores a random connection reference as its secret credential. The reference can use the corresponding authorization on a host that has its matching private file, so keep it confidential.

The plugin adds no analytics or telemetry and does not intentionally log prompts, model responses, OAuth credentials or connection references. Dify and your hosting infrastructure control their own logging and retention. Cenmax AI's service terms and privacy policies govern processing by Cenmax AI; this document makes no separate retention or training guarantees.

Use the helper's logout action to revoke the connection and remove its local session. Separately remove the credential from Dify. Deleting the plugin package does not revoke a connection or erase host backups. Separate operating-system users or credential volumes are required for mutually untrusted deployments; this plugin is not an operating-system security boundary.

Report implementation problems through the repository's support channel without posting credentials or private content.
