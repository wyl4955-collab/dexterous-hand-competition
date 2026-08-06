# Interface Contract

## Units

- Joint angles: radians
- Cartesian positions: metres
- Time: seconds
- Image coordinates: pixels
- Temperature: degrees Celsius

## Vision topics

- `/bean_task/scene` — `competition_interfaces/msg/Scene`
- `/bean_task/debug_image` — `sensor_msgs/msg/Image`
- `/bean_task/vision_health` — `std_msgs/msg/Bool`

## Task topics and services

- `/bean_task/state` — `competition_interfaces/msg/TaskState`
- `/bean_task/start` — `std_srvs/srv/Trigger`
- `/bean_task/stop` — `std_srvs/srv/Trigger`
- `/bean_task/safety_ok` — `std_msgs/msg/Bool`

## Python action contract

Every control function returns `ActionResult` with:

- `ok`
- `code`
- `message`
- `elapsed_sec`

No task code may access underscore-prefixed state in another module.

## Safety contract

When safety becomes false:

1. Do not issue new motion or hand commands.
2. Cancel or let the current adapter stop according to the verified SDK mechanism.
3. Enter a latched error state.
4. Record the reason.
5. Wait for manual inspection and reset.

Do not automatically move to neutral and do not automatically release the tool.

