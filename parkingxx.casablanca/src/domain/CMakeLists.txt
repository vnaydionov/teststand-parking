
add_custom_command (
    OUTPUT Order.cpp Product.cpp Payment.cpp Account.cpp
    AccountReceipt.cpp AccountConsume.cpp
    COMMAND ${YBORM_ROOT}/bin/yborm_gen --domain ${PROJECT_SOURCE_DIR}/src/parkingxx_schema.xml
        ${CMAKE_CURRENT_BINARY_DIR}
    DEPENDS ${PROJECT_SOURCE_DIR}/src/parkingxx_schema.xml
)

add_custom_target (generate_domain DEPENDS
    ${CMAKE_CURRENT_BINARY_DIR}/Order.cpp)

