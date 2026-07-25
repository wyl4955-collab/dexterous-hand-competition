cmake_minimum_required(VERSION 3.10)
project(rh56f2_driver)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(competition_interfaces REQUIRED)

# Protocol library (shared, can be used by other packages)
add_library(rh56f2_protocol SHARED
  src/rs485_protocol.cpp
)
target_include_directories(rh56f2_protocol PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(rh56f2_protocol)
ament_target_dependencies(rh56f2_protocol)

# Driver node executable
add_executable(rh56f2_driver_node
  src/rh56f2_driver_node.cpp
)
target_include_directories(rh56f2_driver_node PRIVATE
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
)
target_link_libraries(rh56f2_driver_node rh56f2_protocol)
ament_target_dependencies(rh56f2_driver_node
  rclcpp
  std_msgs
  competition_interfaces
)

# Install
install(TARGETS rh56f2_protocol rh56f2_driver_node
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/ DESTINATION include)
install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})

ament_package()
