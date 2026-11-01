# Imports AVM v1.0.0 built by scripts/build_avm_lib.ps1 (clang-cl, no LTO) or
# scripts/build_avm_lib.sh (clang, Linux) as target `avm`.
set(AVM_ROOT "$ENV{AVM_ROOT}" CACHE PATH "AVM source tree (tag v1.0.0); defaults to $AVM_ROOT")
if(NOT AVM_ROOT)
  message(FATAL_ERROR "set AVM_ROOT (environment or -DAVM_ROOT=...) to the AVM v1.0.0 source tree")
endif()
set(AVM_LIB_BUILD "${AVM_ROOT}/_build_lib" CACHE PATH "AVM library build directory")

if(WIN32)
  set(_avm_lib "${AVM_LIB_BUILD}/avm.lib")
  set(_avm_glob "*.lib")
  set(_avm_exclude "/avm\\.lib$")
else()
  set(_avm_lib "${AVM_LIB_BUILD}/libavm.a")
  set(_avm_glob "*.a")
  set(_avm_exclude "/libavm\\.a$")
endif()
if(NOT EXISTS "${_avm_lib}")
  message(FATAL_ERROR "${_avm_lib} not found; run scripts/build_avm_lib.ps1 (Windows) or scripts/build_avm_lib.sh (Linux) first")
endif()

# avm.lib's ML-based objects reference TFLite and its dependencies; link every library the AVM build made.
file(GLOB_RECURSE AVM_DEP_LIBS "${AVM_LIB_BUILD}/${_avm_glob}")
list(FILTER AVM_DEP_LIBS EXCLUDE REGEX "${_avm_exclude}")

if(WIN32)
  add_library(avm STATIC IMPORTED GLOBAL)
  set_target_properties(avm PROPERTIES
    IMPORTED_LOCATION "${_avm_lib}"
    INTERFACE_INCLUDE_DIRECTORIES "${AVM_ROOT};${AVM_LIB_BUILD}"
    INTERFACE_LINK_LIBRARIES "${AVM_DEP_LIBS}")
else()
  # GNU ld reads static archives once, in order; the TFLite archives reference each other, so the
  # whole set is one rescanned group.
  add_library(avm INTERFACE IMPORTED GLOBAL)
  set_target_properties(avm PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${AVM_ROOT};${AVM_LIB_BUILD}")
  find_package(Threads REQUIRED)
  target_link_libraries(avm INTERFACE "$<LINK_GROUP:RESCAN,${_avm_lib};${AVM_DEP_LIBS}>"
    Threads::Threads ${CMAKE_DL_LIBS} m)
endif()
