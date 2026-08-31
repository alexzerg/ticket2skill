# Immutable skill version lifecycle

Never overwrite a stale skill artifact. Mark its publication metadata stale, preserve its registry ID and content, generate a complete successor, run both transition replay and full-skill replay, publish the successor under a new ID, and update the current pointer only after both gates pass.
