cmake_minimum_required(VERSION 3.8)
project(competition_interfaces)

find_package(ament_cmake REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/BeanTarget.msg"
  "msg/Scene.msg"
  "msg/TaskState.msg"
  "msg/PowderScene.msg"
  "msg/ScaleReading.msg"
  DEPENDENCIES geometry_msgs std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()

