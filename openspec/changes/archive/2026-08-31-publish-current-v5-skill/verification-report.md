# Verification report

v4 is created by the initial 200-ticket backfill and remains an immutable historical artifact. A Pub/Sub architecture event creates DriftUpdate, invalidates v4 publication metadata, materializes and independently replays a complete v5 TemporalSkill, publishes v5 under a new registry ID, updates the Firestore current pointer, and switches UI downloads and routing to v5.
