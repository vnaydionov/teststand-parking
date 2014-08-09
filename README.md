teststand-parking
=================

This is a mini-project that simulates parking meter functions.
It's a typical OLTP application, it showcases the typical usage scenario
of object-relational mapper.  Here are two implementations
 * Python with SQLAlchemy
 * C++ with YB.ORM.

The application consists of a minimal HTTP server.
The server handles GET/POST requests of the following types:
 * /get_service_info
 * /create_reservation
 * /pay_reservation
 * /cancel_reservation
 * /stop_service
 * /get_user_account
 * /account_transfer
 * /issue_ticket
 * /leave_parking
 * /check_plate_number

See the unit tests for the protocol documentation.


