cmake_minimum_required(VERSION 3.16)

# Version is read from the Python package so the two never drift.
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/src/mu2edaq_commandline_tools/__init__.py" _init_py)
string(REGEX MATCH "__version__ = \"([0-9]+\\.[0-9]+\\.[0-9]+)\"" _m "${_init_py}")
set(MU2EDAQ_CLI_VERSION "${CMAKE_MATCH_1}")
if(NOT MU2EDAQ_CLI_VERSION)
  message(FATAL_ERROR "could not parse __version__ from src/mu2edaq_commandline_tools/__init__.py")
endif()

project(mu2edaq-commandline-tools VERSION ${MU2EDAQ_CLI_VERSION} LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "Build type" FORCE)
endif()

include(GNUInstallDirs)
include(CTest)

# ------------------------------------------------------------------ library --

add_library(mu2edaq_cli_core src/cpp/mu2edaq_cli_core.cpp)
add_library(mu2edaq::cli_core ALIAS mu2edaq_cli_core)

target_include_directories(mu2edaq_cli_core
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
target_compile_definitions(mu2edaq_cli_core
  PRIVATE MU2EDAQ_CLI_VERSION="${MU2EDAQ_CLI_VERSION}")
set_target_properties(mu2edaq_cli_core PROPERTIES
  VERSION ${PROJECT_VERSION}
  SOVERSION ${PROJECT_VERSION_MAJOR}
  POSITION_INDEPENDENT_CODE ON
)

# GCC < 9 and Clang < 9 keep std::filesystem in a separate library.
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 9.0)
  target_link_libraries(mu2edaq_cli_core PUBLIC stdc++fs)
elseif(CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND CMAKE_CXX_COMPILER_VERSION VERSION_LESS 9.0)
  target_link_libraries(mu2edaq_cli_core PUBLIC c++fs)
endif()

# --------------------------------------------------------------- executable --

add_executable(mu2edaq-tools-info src/cpp/mu2edaq_tools_info.cpp)
target_link_libraries(mu2edaq-tools-info PRIVATE mu2edaq_cli_core)
target_compile_definitions(mu2edaq-tools-info
  PRIVATE MU2EDAQ_CLI_VERSION="${MU2EDAQ_CLI_VERSION}")

# -------------------------------------------------------------------- tests --

if(BUILD_TESTING)
  # CppUnit is the preferred harness; without it the same assertions run
  # through a plain assert()-based driver so `ctest` still covers the library.
  find_package(PkgConfig QUIET)
  if(PkgConfig_FOUND)
    pkg_check_modules(CPPUNIT QUIET cppunit)
  endif()

  add_executable(test_cli_core tests/cpp/test_cli_core.cpp)
  target_link_libraries(test_cli_core PRIVATE mu2edaq_cli_core)
  if(CPPUNIT_FOUND)
    target_compile_definitions(test_cli_core PRIVATE HAVE_CPPUNIT=1)
    target_include_directories(test_cli_core PRIVATE ${CPPUNIT_INCLUDE_DIRS})
    target_link_libraries(test_cli_core PRIVATE ${CPPUNIT_LIBRARIES})
    target_link_directories(test_cli_core PRIVATE ${CPPUNIT_LIBRARY_DIRS})
  endif()
  add_test(NAME cli_core COMMAND test_cli_core)

  add_test(NAME tools_info_help COMMAND mu2edaq-tools-info --help)
endif()

# ------------------------------------------------------------------ install --

install(TARGETS mu2edaq_cli_core mu2edaq-tools-info
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
install(FILES src/include/mu2edaq_cli_core.hpp
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(DIRECTORY man/man1/
  DESTINATION ${CMAKE_INSTALL_MANDIR}/man1
  FILES_MATCHING PATTERN "*.1")
install(DIRECTORY man/man3/
  DESTINATION ${CMAKE_INSTALL_MANDIR}/man3
  FILES_MATCHING PATTERN "*.3")
install(FILES config/mu2edaq-commandline-tools.yaml
  DESTINATION ${CMAKE_INSTALL_SYSCONFDIR}/mu2edaq
  RENAME commandline-tools.yaml)
