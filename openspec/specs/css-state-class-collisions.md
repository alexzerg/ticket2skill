# CSS state-class collisions

Generic state classes such as `.current` and `.stale` must be scoped to their component. Reusing them on both badges and container cards can leak pill styling such as `border-radius: 999px` into full layouts. Geometry tests should assert computed radius, equal height, and overflow—not only class presence.
