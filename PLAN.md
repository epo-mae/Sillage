# Sillage implementation plan

Build a responsive, server-backed MVP using Flask, Waitress, SQLite, and accessible plain JavaScript. SQLite suits a single-host personal application; move to PostgreSQL for multi-instance deployment. Accounts use salted scrypt password hashes and signed, HttpOnly sessions. Persist collections, preferences, imported events, immutable recommendation snapshots, wear records and feedback.

1. Define versioned schema and metadata validation. Start empty; offer clearly fictional example profiles only by explicit request.
2. Implement weather provider abstraction, cached Open-Meteo forecasts, optional ICS calendar import, local timezone and hemisphere-aware context/horizon calculation. Missing signals remain absent.
3. Score known attributes using normalized configurable weights, apply hard penalties, bounded rotation and gradually weighted personal feedback. Separate confidence from suitability and preserve every breakdown.
4. Build recommendation, collection, journal and settings views, including all empty/error/loading states and contextual explanations.
5. Verify deterministic engine scenarios and authenticated end-to-end persistence; document setup and integration limitations.

No AI credentials required. Explanations are generated from actual score data. Calendar import supports one-off VEVENTs and expanded exports; recurring rules that need expansion are rejected with a useful error. OAuth calendar connections, destination forecasting, AI classification and native clients are later work. Fragrance characteristics are user-entered estimates, never purported verified catalog facts. Initial location is unset and weather unavailable until consent or manual coordinates. Authentication is local account authentication; email verification and recovery require a future transactional mail provider.
