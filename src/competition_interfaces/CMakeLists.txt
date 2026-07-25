cmake_minimum_required(VERSION 3.10)
project(competition_interfaces)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(action_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
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
  DEPENDENCIES
    action_msgs
    geometry_msgs
    sensor_msgs
    std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
