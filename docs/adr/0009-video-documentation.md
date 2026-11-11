# ADR 0009: Single-document video walkthrough

Date: 2026-11-09

Status: Accepted (documentation only)

The user requested one detailed video description covering the project and its features. Deliver a Word document containing narration, screen directions, feature explanations, recording sequence, publishing text, glossary, and source notes. Keep implemented behavior distinct from illustrative examples, historical tests, and deferred work.

The deliverable is `docs/Tollgate-Complete-Video-Description.docx`. It changes no architecture or application behavior and authorizes no recording, publishing, external delivery, or provider calls.

## Illustrated edition

At the user’s follow-up request, embed eight existing demo screenshots and four explanatory diagrams in the same Word deliverable. Label screenshot provenance and illustrative examples. Retain Markdown source and diagram assets for future updates; no new runtime capture or provider calls are required.

## Portable HTML edition

At the user’s request, add a standalone HTML edition with embedded data-URL images and CSS, system fonts, anchor navigation and responsive/print styles. Recipients need only the HTML file; no asset folder, service, external font, or network connection is required.
