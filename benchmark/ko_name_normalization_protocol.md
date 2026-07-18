# Knowledge Object Name Normalization Protocol

**Version:** ko_name_normalization_protocol_v0.1
**Status:** Frozen for 002C-1 deterministic development evaluation

## Purpose

Name normalization creates a conservative comparison key for deterministic KO
identity candidates. It is not stemming, semantic similarity, alias discovery,
or identity adjudication.

## Ordered Operations

Version v0.1 applies only:

1. Unicode NFKC normalization;
2. Unicode apostrophe variants to ASCII apostrophe;
3. Unicode dash variants to ASCII hyphen;
4. leading and trailing whitespace removal;
5. removal of one complete, balanced outer presentation wrapper;
6. internal whitespace compression;
7. Unicode-aware case folding.

Allowed outer wrappers are Markdown bold, Markdown inline code, `$...$`,
`\(...\)`, and `\[...\]`. Wrapper removal is allowed only when the wrapper
encloses the complete non-empty name.

## Prohibited Operations

Version v0.1 does not:

- stem or lemmatize words;
- merge singular and plural forms;
- expand abbreviations;
- remove semantic words such as `method`, `formula`, `theorem`, or `vector`;
- perform fuzzy string matching;
- inspect mention IDs, Ground Truth clusters, or evaluation errors;
- merge different KO types.

Aliases are a separate, explicitly bound method resource. Ground Truth aliases
must never be used as a runtime alias dictionary.

## Audit Contract

Every mention records its original name, normalized key, ordered operations
that changed the string, KO type, and assigned predicted cluster. Empty
normalized names are fatal.
