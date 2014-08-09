# -*- coding: utf-8 -*-

import sys
import json
import BaseHTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from urlparse import urlparse
from urllib import unquote
import logging

import core

log = logging.getLogger('server')
http_log = logging.getLogger('http')

class ParkingHTTPRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        http_log.info(format, *args)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            func_name = parsed.path.split('/')[-1]
            def mk_param(s):
                def unq(t): return unquote(t.replace('+', ' '))
                parts = s.split('=', 1)
		return (unq(parts[0]), unq(''.join(parts[1:])))
            query = dict(mk_param(i) for i in parsed.query.split('&') if i)
            def expand_service_descr(k, v):
                if k == 'service_descr':
                    v = json.loads(v)
                return (k, v)
            query = dict(expand_service_descr(k, v) for k, v in query.iteritems())
            log.info('func_name=%s, query=%s' % (func_name, repr(query)))
            assert func_name in core.api_functions
            func = getattr(core, func_name)
            resp_data = func(**query)
            resp = json.dumps(resp_data)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        except:
            log.exception('')
            resp = 'Internal server error'
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

def run_server():
    ServerClass  = BaseHTTPServer.HTTPServer
    HandlerClass = ParkingHTTPRequestHandler
    HandlerClass.protocol_version = 'HTTP/1.0'
    if sys.argv[1:]:
        port = int(sys.argv[1])
    else:
        port = 8111
    server_address = ('127.0.0.1', port)
    httpd = ServerClass(server_address, HandlerClass)
    sa = httpd.socket.getsockname()
    log.info('Serving HTTP forever on %s port %s' % (sa[0], sa[1]))
    httpd.serve_forever()

if __name__ == '__main__':
    logging.basicConfig(
            filename='parking.log',
            format='%(asctime)s %(thread)d %(levelname)s %(name)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.DEBUG)
    sql_logger = logging.getLogger('sqlalchemy.engine')
    sql_logger.setLevel(logging.DEBUG)
    run_server()

