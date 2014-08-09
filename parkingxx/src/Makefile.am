
SUBDIRS=domain
AUTOMAKE_OPTIONS = subdir-objects

AM_CXXFLAGS=\
	-I $(top_srcdir)/lib \
	$(XML_CPPFLAGS) \
	$(BOOST_CPPFLAGS) \
	$(SQLITE3_CFLAGS) \
	$(SOCI_CXXFLAGS) \
	$(YBORM_CXXFLAGS) \
	$(WX_CFLAGS) \
	$(QT_CFLAGS)

bin_PROGRAMS=parkingxx
bin_SCRIPTS=parkingxx.sh

parkingxx_SOURCES=\
	domain/Product.cpp \
	domain/Order.cpp \
	domain/Account.cpp \
	domain/Payment.cpp \
	domain/AccountReceipt.cpp \
	domain/AccountConsume.cpp \
	domain/AccountTransfer.cpp \
	tcp_socket.cpp \
	micro_http.cpp \
	app_class.cpp \
	helpers.cpp \
	main.cpp

parkingxx_LDFLAGS=\
	$(XML_LIBS) \
	$(BOOST_THREAD_LDFLAGS) \
	$(BOOST_THREAD_LIBS) $(BOOST_DATE_TIME_LIBS) \
	$(ODBC_LIBS) \
	$(SQLITE3_LIBS) \
	$(SOCI_LIBS) \
	$(WX_LIBS) \
	$(QT_LDFLAGS) \
	$(QT_LIBS) \
	$(EXECINFO_LIBS) \
	$(YBORM_LDFLAGS) \
	$(YBORM_LIBS)

