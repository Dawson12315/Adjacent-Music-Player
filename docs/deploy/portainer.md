# Deploy on Portainer

[← Back to the README](../../README.md)

Same YAML as the [Docker CLI guide](docker-cli.md) — Portainer reads standard compose.

1. **Stacks → Add stack**, name it `adjacent`.
2. Paste the YAML into the web editor.
3. Replace `YOUR_IP`, the secret, and the two volume paths.
4. **Deploy the stack.**

Create the data directory and fix its owner *before* deploying — Portainer will
not do it for you, and the backend cannot create a directory it may not write:

```bash
sudo mkdir -p /opt/apps/adjacent
sudo chown -R 1000:1000 /opt/apps/adjacent
```

**Updating, and the one thing that catches everyone:** Portainer redeploys with
the `:latest` image *it already has locally*. Pressing Update alone will report
success and change nothing.

**Stacks → adjacent → Update the stack → enable "Re-pull image and redeploy" →
Update.** That toggle is the entire difference between an update and a no-op.

To confirm you actually moved:

```bash
docker inspect adjacent-backend --format '{{.Image}}'
```
