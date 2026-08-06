# Four-Person Bean-Picking Team Guide

## Member A — robot motion

### Deliverables

- Cache arm/head/waist/leg feedback with timestamps.
- Check joint limits before every command.
- Interpolate every trajectory; never jump to a distant target.
- Return a structured result for every action.
- Record and load named poses from YAML.
- Calibrate a 3×3 source-container workspace with hover/pick/lift layers.
- Reject targets outside the calibrated polygon.

### Acceptance

- No feedback means no motion.
- Out-of-limit goals publish nothing.
- Every action has a timeout.
- Each named pose repeats 10 times at low speed without collision.
- The task layer never needs to know raw joint IDs.

## Member B — vision and calibration

### Deliverables

- Collect at least 50 synchronized color/depth samples from the real camera pose.
- Detect soybeans only inside the source-container ROI.
- Produce HSV masks and debug images for every test.
- Calibrate pixel-to-table coordinates with a homography.
- Verify whether depth is aligned to color before indexing depth pixels.
- Rank targets by edge clearance, isolation, workspace center and failure history.
- Publish `Scene` with a timestamp, validity and confidence.

### Acceptance

- Table-coordinate error target is at most 5 mm.
- Calibration or image timeout produces `valid=false`.
- Containers, shadows and tweezers are not counted as beans.
- The detector can be evaluated offline without the robot moving.

## Member C — hand and tweezer skills

### Deliverables

- Verify the actual Inspire Hand service types and finger order.
- Validate every array length and ratio range before service calls.
- Calibrate `open`, `tweezers_pregrasp`, `tweezers_hold`, `tweezers_squeeze`, `tweezers_release` and `release_tool`.
- Implement `grasp_tweezer`, `squeeze_bean`, `release_bean` and `release_tweezer` skills.
- Calibrate the tweezer tip TCP and pick height.

### Acceptance

- Tweezers remain held for five minutes.
- Fifty hold/squeeze/release cycles do not drop the tool.
- Releasing a bean does not release the tweezers.
- Every service call returns success, failure or timeout.
- A failed tweezer grasp prevents bean-picking motion.

## Member D — FSM, safety and integration

### Deliverables

- Keep the ROS2 executor spinning while the task runs.
- Maintain the interface package, launch files and config loading.
- Implement start/stop services and the timer-driven FSM.
- Monitor hard estop, remote estop, power, joint errors, stale feedback, stale vision, temperature, current and action timeout.
- Stop new commands and latch an error on any safety trigger.
- Save logs, rosbag paths, debug-image paths, config and Git version for every run.

### Acceptance

- `colcon build --symlink-install` succeeds.
- Every state has a timeout and explicit transition.
- Stale scene/feedback is rejected.
- A safety trigger never initiates an automatic neutral motion or tool release.
- A mock run reaches every state before real hardware is connected.

## Integration order

1. D validates build, config, executor and safety latch.
2. A validates status and one low-speed joint.
3. C validates hand poses without a tool.
4. B validates vision without robot motion.
5. A+C complete M1 with manually mounted tweezers and one fixed bean.
6. B+A+D complete M2 with one visually selected bean.
7. A+C+D complete M3 automatic tweezer pickup.
8. All members complete M4, fault injection and five-minute runs.

## Git branches

```text
main             field-verified releases only
dev              daily integration
feat/motion      member A
feat/vision      member B
feat/tweezers    member C
feat/system      member D
```

One owner per file. Public interface changes require all four members to be notified before merging.

