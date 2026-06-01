-- Free-form, unstructured per-event labels (e.g. a venue's genre tags like
-- "Bossa Nova", "Vocal Jazz"). A catch-all bag of strings that scrapers may
-- populate; not used for top-level category/filtering yet, preserved for future
-- richer display/filtering. Defaults to an empty array so the column is never NULL.
ALTER TABLE event ADD COLUMN annotations TEXT[] NOT NULL DEFAULT '{}';
