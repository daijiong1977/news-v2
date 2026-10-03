# 2026-10-03 — reader derived PDF consistency

Severity: high; Area: shadow pipeline; Status: fixed; Keywords: PDF, artifacts, resume

## Symptom

Oracle evening-poc-1 completed nine articles but stopped before CI with
`Reader content differs from the nine ready articles`. No website or DB write occurred.

## Root cause

`build_reader` adds 18 PDFs from approved details. `kidsnews_bot.artifacts` compared
all public content against the internal ZIP, which does not contain those derivatives.
The existing full-artifact regression reproduces this failure with the PDF-enabled build.

## Fix and invariant

PR86: regenerate deterministic PDFs from approved internal details before the
exact byte comparison. Do not merely ignore PDF files or weaken content hashes.
Resume the same directory and reuse model answers.

## Pinning test

`pipeline/test_source_first_deepseek.py::test_fixed_group_zip_official_reader_delivery_is_idempotent`
now checks 18 PDFs and rejects a changed PDF even with an updated consistent manifest.
Python3.10 related suite: 36 passed; strengthened targeted regression: 1 passed.
