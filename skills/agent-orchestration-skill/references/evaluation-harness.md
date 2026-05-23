# Evaluation Harness

Run these checks after changing this skill pack:

1. Exactly one discoverable repo skill.
2. All worker agents have explicit reasoning effort and leaf-worker guards.
3. Small known-file task recommends zero or one worker, not a wave.
4. Scout/file discovery uses low reasoning.
5. Normal writing uses medium reasoning.
6. Complex implementation uses high reasoning.
7. Very large planning may use xhigh, preferably read-only.
8. Context Capsule renders compactly.
9. Context Coverage Gate rejects handoffs missing required files.
10. Handoff Validator rejects nested delegation leakage.
11. Plan Gate accepts a valid compact DAG and rejects vague phases.
12. Budget Governor rejects excessive fan-out.
