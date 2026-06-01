-- Some events have multiple showtimes on the same day (e.g. Jamboree's
-- "19:00h / 21:00h"). `start_time` remains the EARLIEST session (used for
-- chronological ordering); `start_times` holds ALL sessions and is always
-- populated, even for single-session events (so readers have one code path:
-- render `start_times` joined by " / "). Defaults to empty so it is never NULL.
ALTER TABLE event ADD COLUMN start_times TIME[] NOT NULL DEFAULT '{}';
