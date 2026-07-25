cmake_minimum_required(VERSION 3.10)
project(competition_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_cmake REQUIRED)
find_package(rosidl_generator_c REQUIRED)
find_package(rosidl_generator_cpp REQUIRED)
find_package(rosidl_generator_py REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/HandState.msg"
  "msg/HandCommand.msg"
  "msg/BeanDetection.msg"
  "msg/BeanDetections.msg"
  "msg/ToolState.msg"
  "msg/TaskStatus.msg"
  "srv/HandCalibrate.srv"
  "srv/RunTask.srv"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_generator_c rosidl_generator_cpp rosidl_generator_py)
ament_package()
