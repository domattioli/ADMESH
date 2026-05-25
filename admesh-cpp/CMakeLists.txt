cmake_minimum_required(VERSION 3.12)
project(admesh_cpp VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find dependencies
find_package(Eigen3 3.3 CONFIG REQUIRED)

# Source files
set(ADMESH_SOURCES
    src/api/triangulate.cpp
    src/io/fort14.cpp
    src/io/loaders.cpp
    src/io/boundary_type.cpp
    src/stages/routine.cpp
    src/stages/background_grid.cpp
    src/stages/distance.cpp
    src/stages/curvature.cpp
    src/stages/medial_axis.cpp
    src/stages/bathymetry.cpp
    src/stages/dominate_tide.cpp
    src/stages/boundary.cpp
    src/stages/mesh_size.cpp
    src/stages/distmesh.cpp
    src/stages/quality.cpp
    src/stages/in_polygon.cpp
    src/stages/inpaint.cpp
)

# Static library
add_library(admesh STATIC ${ADMESH_SOURCES})
target_include_directories(admesh
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)
target_link_libraries(admesh PUBLIC Eigen3::Eigen)

# Compiler flags: bit-parity stages get -fno-fast-math -ffp-contract=off
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(admesh PRIVATE
        $<$<CONFIG:Release>:-O3 -funroll-loops>
        -fno-fast-math
        -ffp-contract=off
    )
elseif(CMAKE_CXX_COMPILER_ID MATCHES "MSVC")
    target_compile_options(admesh PRIVATE
        $<$<CONFIG:Release>:/O2>
        /fp:precise
    )
endif()

# Install
install(
    DIRECTORY include/admesh
    DESTINATION include
)
install(
    TARGETS admesh
    EXPORT admesh-targets
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)
install(
    EXPORT admesh-targets
    FILE admesh-targets.cmake
    NAMESPACE admesh::
    DESTINATION lib/cmake/admesh
)

# ctest
enable_testing()
add_subdirectory(tests)
