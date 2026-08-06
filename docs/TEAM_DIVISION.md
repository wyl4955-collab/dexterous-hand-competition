# Four-Person Bean-Picking Team Guide

## Member A — robot motion and motion safety

### Deliverables

- Cache arm/head/waist/leg feedback with timestamps.
- Check joint limits before every command.
- Interpolate every trajectory; never jump to a distant target.
- Return a structured result for every action.
- Record and load named poses from YAML.
- Calibrate a 3×3 source-container workspace with hover/pick/lift layers.
- Reject targets outside the calibrated polygon.
- Own the safety latch for estop, power, joint errors and stale feedback.

### Acceptance

- No feedback means no motion.
- Out-of-limit goals publish nothing.
- Every action has a timeout.
- Each named pose repeats 10 times at low speed without collision.
- The task layer never needs to know raw joint IDs.

## Member B — vision, calibration and perception interfaces

### Deliverables

- Collect at least 50 synchronized color/depth samples from the real camera pose.
- Detect soybeans only inside the source-container ROI.
- Produce HSV masks and debug images for every test.
- Calibrate pixel-to-table coordinates with a homography.
- Verify whether depth is aligned to color before indexing depth pixels.
- Rank targets by edge clearance, isolation, workspace center and failure history.
- Publish `Scene` with a timestamp, validity and confidence.
- Own `BeanTarget`/`Scene` fields together with C2 as the consumer reviewer.

### Acceptance

- Table-coordinate error target is at most 5 mm.
- Calibration or image timeout produces `valid=false`.
- Containers, shadows and tweezers are not counted as beans.
- The detector can be evaluated offline without the robot moving.

## Member C1 — low-level hand control and tweezer holding

### Deliverables

- Verify the actual Inspire Hand service types and finger order.
- Validate every array length and ratio range before service calls.
- Calibrate `open`, `tweezers_pregrasp`, `tweezers_hold`, `tweezers_squeeze`, `tweezers_release` and `release_tool`.
- Provide validated position/force/speed and named hand-pose interfaces.
- Calibrate the tweezer tip TCP, holding pose and opening ratios.

### Acceptance

- Tweezers remain held for five minutes.
- Fifty hold/squeeze/release cycles do not drop the tool.
- Releasing a bean does not release the tweezers.
- Every service call returns success, failure or timeout.
- C2 can implement all skills using only C1's public interfaces.

## Member C2 — tweezer skills, FSM and lightweight integration

### Deliverables

- Keep the ROS2 executor spinning while the task runs.
- Compose A and C1 interfaces into reusable tweezer skills.
- Maintain launch files and config loading.
- Implement start/stop services and the timer-driven FSM.
- Consume A's safety latch, B's vision health and C1's hand health.
- Stop new commands and enter an error lock on any safety trigger.
- Save logs, rosbag paths, debug-image paths, config and Git version for every run.

### Acceptance

- `colcon build --symlink-install` succeeds.
- Every state has a timeout and explicit transition.
- Stale scene/feedback is rejected.
- A safety trigger never initiates an automatic neutral motion or tool release.
- A mock run reaches every state before real hardware is connected.

## Former D work distribution

| Work | New owner |
|---|---|
| Estop, power, joint errors, feedback timeout, `safety_monitor.py` | A; C1 reviews hand safety |
| `BeanTarget` and `Scene` definitions | B; C2 reviews consumption |
| Executor, FSM, launch, startup and run-id logging | C2 |
| Package dependencies | The module owner; C2 checks integration |
| Git merge and tags | C2 executes; A reviews |

## Integration order

1. C2 validates build, config, executor and the mock FSM.
2. A validates status, motion safety and one low-speed joint.
3. C1 validates hand poses without a tool.
4. B validates vision without robot motion.
5. A+C1+C2 complete M1 with manually mounted tweezers and one fixed bean.
6. A+B+C2 complete M2 with one visually selected bean.
7. A+C1+C2 complete M3 automatic tweezer pickup.
8. All members complete M4, fault injection and five-minute runs.

## Git branches

```text
main             field-verified releases only
dev              daily integration
feat/motion-safety      member A
feat/vision-interfaces  member B
feat/hand-control       member C1
feat/tweezer-task       member C2
```

One owner per file. Public interface changes require all four members to be notified before merging.
