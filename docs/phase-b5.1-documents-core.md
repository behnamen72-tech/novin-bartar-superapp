# Phase B5.1 Documents Core

Implemented foundation:
- Document metadata
- Document versions
- Storage abstraction
- Local storage provider
- Entity links
- Document permissions

Architecture decisions:
- Document does not directly depend on business modules.
- Links are polymorphic through DocumentLink.
- Audit remains independent.
- Physical deletion is not part of the model.

Next:
B5.2 APIs + Authorization + practical UI.
