
BUILT_SOURCES=Order.cpp parkingxx_schema.sql

SCHEMA=$(top_srcdir)/src/parkingxx_schema.xml

Order.cpp: $(SCHEMA)
	@YBORM_GEN@ --domain $(SCHEMA) ./

parkingxx_schema.sql: $(SCHEMA)
	@YBORM_GEN@ --ddl $(SCHEMA) "@YBORM_DBTYPE@" $@

clean-local:
	-rm -f *.cpp *.h *.sql

