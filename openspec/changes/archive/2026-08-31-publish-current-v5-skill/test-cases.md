# Test cases

- v4 and v5 receive different registry IDs and artifact URLs.
- v5 supersedes v4 and records the architecture event.
- v5 patch uses jenkins.clouds[].kubernetes.templates[] and ci-build-agent.
- v5 patch has no iam.gke.io annotation or gcp-project placeholder.
- After drift, router and download use v5 while v4 remains addressable as stale history.
