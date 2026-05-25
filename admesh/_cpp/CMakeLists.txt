cmake_minimum_required(VERSION 3.12)
project(admesh_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)
find_package(Eigen3 CONFIG REQUIRED)

pybind11_add_module(_distmesh_cpp
    distmesh_module.cpp
    distmesh_cpp.cpp
)

target_link_libraries(_distmesh_cpp PRIVATE Eigen3::Eigen)

# Install target: placed in admesh/_cpp/ for import
install(TARGETS _distmesh_cpp DESTINATION admesh/_cpp)
