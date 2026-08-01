# ForgeGov v2.1.0 Collaboration + AI Foundation

## Added
- Secure Project Rooms owned by one organization and selectively shared with partner organizations.
- Partner access controls for uploads, comments, and pricing visibility.
- Persistent AI conversations and messages with internal or shared Project Room visibility.
- Custom free-text job titles separated from security roles.
- Project Rooms navigation and creation interface.

## Fixed
- SBA SUBNet defaults to 20 opportunities per page.
- SUBNet pagination cache and database fallback now respect page size.
- SUBNet opportunities can be added directly to the standard ForgeGov pipeline.
- Federal forecast cards use compact agency headings and non-fabricated status labels.

## Security
- Partner companies can access only explicitly shared Project Rooms.
- Only the owning organization can modify/delete a room or manage partner access.
- Shared AI conversations remain bound to Project Room visibility.

## Validation note
Python source and migration files pass compile/AST validation. The Next.js production build could not be executed in the build environment because its internal npm mirror did not contain `zod-validation-error@4.0.2`; no source-level frontend error was reported before dependency installation failed.
