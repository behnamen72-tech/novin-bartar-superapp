# Shared Artifact Governance — Single Editor / Single Canonical Baseline

Effective: 2026-09-13
Scope: Novin Bartar Super App ↔ Enferadi Market / Customer Platform

## Purpose

Shared cross-track artifacts must never be edited independently in both tracks.
The Integration Contract v1.1 fork proved that technically sound parallel edits can
still create an authority failure when two artifacts carry the same semantic version.

## Core rule

Every shared artifact has exactly **one Editing Owner** at a time.

- The Editing Owner publishes the canonical working artifact.
- The other track may submit change requests, review comments, patches, or proposed
  text, but must not publish a competing artifact with the same canonical version.
- A shared version is canonical only when its registry entry identifies one artifact
  hash and the required architecture review has approved that exact artifact.
- A hash that has been retired remains recorded as `RETIRED / DO NOT USE`; it is not
  silently deleted from governance history.

## Version rule

A competing rewrite must not reuse an already canonical version identifier.

- Compatible correction to an un-frozen draft: update the owner-controlled draft.
- Incompatible or substantial post-freeze change: create a new version (`v1.2`, etc.).
- New version requires a new primary artifact/hash and architecture review.

## Required registry fields

Every shared artifact registry entry must record:

- artifact name;
- semantic/version identifier;
- Editing Owner;
- consuming track(s);
- canonical path or package;
- SHA-256 / commit SHA;
- review status and primary review reference;
- lifecycle: `DRAFT`, `REVIEW`, `FROZEN`, `RETIRED`;
- superseded/retired hashes where applicable;
- open production gates not closed by architecture freeze.

## Change-request workflow

1. Non-owner track opens a change request.
2. Editing Owner incorporates or rejects the request in the single canonical draft.
3. If the artifact is already frozen and the change is incompatible/material, bump version.
4. Produce new immutable hash.
5. Claude reviews the primary artifact for shared architecture gates.
6. Registry is updated only after the exact reviewed hash is known.

## Current canonical Integration Contract

- Artifact: `api-integration-contract-v1.1-FROZEN.md`
- Editing Owner: **Super App / Joint Integration Architecture owner** until formally reassigned.
- Consumers: Super App and Customer Platform.
- SHA-256: `903a5c649bf8d3e5f16998405fcb687d8bf07a427f793c35fc9a8b74e608f59f`
- Lifecycle: `FROZEN`
- Claude verdict: `APPROVED FOR FREEZE`
- Retired competing v1.1 hash: `542eabec901129bdb1f34b6155188b955503d3c1d2576553ec0e230960b7fa3d`
- Retired reason: competing v1.1 baseline / provenance fork.

The five pre-production gates listed by the canonical Contract remain open; artifact
freeze does not imply production readiness.
