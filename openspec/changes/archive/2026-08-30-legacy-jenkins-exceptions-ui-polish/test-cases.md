# Test cases

## Scenario: default incident
Given an incident with no allowlisted legacy controller
When the current skill resolves it
Then VM SSH/systemctl guidance remains stale and the GitOps/GKE path is selected.

## Scenario: controlled legacy exception
Given a target equal to jenkins-paris, jenkins-barcelona, or jenkins-NYC
When the skill routes the incident
Then the scoped VM runbook is allowed only for that target.

## Scenario: visual rendering
Given the four-era timeline and drift comparison
When rendered on desktop and mobile
Then the current-era card does not inherit badge styling and the comparison remains readable.
