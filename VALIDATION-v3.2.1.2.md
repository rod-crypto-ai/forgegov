# ForgeGov v3.2.1.2 Validation

Run:

```bash
./VERIFY_V3.2.1.2.command
```

The release is cleared only when the full 24-stage gate completes successfully and ends with:

```text
ForgeGov v3.2.1.2 validation completed successfully.
```

The Microsoft regression stage must prove:

- OAuth PKCE initiation
- callback state/code persistence to `ConnectedApp`
- Graph-backed verification metadata
- callback error visibility
- user/workspace isolation
- Viewer external-action restrictions
- subcontract workspace isolation
