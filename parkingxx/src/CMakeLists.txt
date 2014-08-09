
add_subdirectory (domain)

include_directories (
    ${ICONV_INCLUDES}
    ${LIBXML2_INCLUDES}
    ${BOOST_INCLUDEDIR}
    ${YBORM_INCLUDES}
    ${CMAKE_CURRENT_BINARY_DIR})

add_executable (parkingxx
    tcp_socket.cpp micro_http.cpp app_class.cpp helpers.cpp main.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/Product.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/Order.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/Account.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/Payment.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/AccountReceipt.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/AccountConsume.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/AccountTransfer.cpp)

set_source_files_properties (
	${CMAKE_CURRENT_BINARY_DIR}/domain/Product.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/Order.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/Account.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/Payment.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/AccountReceipt.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/AccountConsume.cpp
	${CMAKE_CURRENT_BINARY_DIR}/domain/AccountTransfer.cpp
    PROPERTIES GENERATED 1)

add_dependencies (parkingxx generate_domain)

if (UNIX)
target_link_libraries (parkingxx ${YBORM_LIB} ${YBUTIL_LIB} ${LIBXML2_LIBS}
    ${YB_BOOST_LIBS} ${ODBC_LIBS}
    ${SQLITE3_LIBS} ${SOCI_LIBS} ${QT_LIBRARIES})
else ()
target_link_libraries (parkingxx ${YBORM_LIB} ${YBUTIL_LIB} ${LIBXML2_LIBS}
    ${YB_BOOST_LIBS} ${ODBC_LIBS}
    ${SQLITE3_LIBS} ${SOCI_LIBS} ${QT_LIBRARIES} ${SOCKET_LIB})
endif ()

install (TARGETS parkingxx DESTINATION bin)
install (FILES parkingxx.bat DESTINATION bin)
install (FILES parkingxx_schema.xml DESTINATION shared)

