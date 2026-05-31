add_executable(test_mesh_mvp test_mesh_mvp.cpp)
target_link_libraries(test_mesh_mvp PRIVATE admesh)
add_test(NAME test_mesh_mvp COMMAND test_mesh_mvp)

add_executable(test_wnat_timing test_wnat_timing.cpp)
target_link_libraries(test_wnat_timing PRIVATE admesh)
add_test(NAME test_wnat_timing COMMAND test_wnat_timing)
