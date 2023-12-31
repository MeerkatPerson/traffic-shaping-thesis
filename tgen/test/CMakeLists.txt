## build the mmodel test binary

include_directories(AFTER ../src/ ${M_INCLUDES} ${GLIB_INCLUDE_DIRS} ${IGRAPH_INCLUDE_DIRS})

## build as position-independent so it can run in Shadow
add_definitions(-D_GNU_SOURCE)
add_compile_options(-O2 -ggdb -fno-omit-frame-pointer -fPIC -std=gnu11)

## CFLAGS status update
message(STATUS "CMAKE_C_FLAGS = ${CMAKE_C_FLAGS}")

set(tgen_sources
	test-markovmodel.c
    ../src/tgen-log.c
    ../src/tgen-markovmodel.c
)

## build the tgen executable
add_executable(test-mmodel ${tgen_sources})

## this ensures it is linked as a position-independent executable so that
## the system calls can be intercepted (so that it works in Shadow)
## this is OK because none of tgen's internal symbols need to be interposed!
set_target_properties(test-mmodel PROPERTIES 
        INSTALL_RPATH ${CMAKE_INSTALL_PREFIX}/lib 
        INSTALL_RPATH_USE_LINK_PATH TRUE 
        LINK_FLAGS "-pie -rdynamic -Wl,--no-as-needed")

## link in our dependencies and install
target_link_libraries(test-mmodel ${M_LIBRARIES} ${IGRAPH_LIBRARIES} ${GLIB_LIBRARIES})
