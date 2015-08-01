# -*- coding: utf-8 -*-

import json
import urlparse
import logging
import core


log = logging.getLogger('server')
http_log = logging.getLogger('http')
log_init = False


def get_request_body(environ):
    request_body = ''
    sz = int(environ.get('CONTENT_LENGTH') or 0)
    if sz:
        request_body = environ['wsgi.input'].read(sz)
    return request_body


def parse_qs(t):
    return {k: ''.join(v) for k, v in
            urlparse.parse_qs(t, keep_blank_values=False,
                              strict_parsing=False).iteritems()}


def init_log():
    logging.basicConfig(
        filename='parking.log',
        format='%(asctime)s %(thread)d %(levelname)s %(name)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.DEBUG)
    sql_logger = logging.getLogger('sqlalchemy.engine')
    sql_logger.setLevel(logging.DEBUG)


def application(environ, start_response):
    try:
        global log_init
        if not log_init:
            init_log()
            log_init = True
        body = get_request_body(environ)
        qs = environ['QUERY_STRING']
        query = parse_qs(qs)
        method = environ['REQUEST_METHOD']
        if method == 'POST':
            query.update(parse_qs(body))
        func_name = environ['PATH_INFO'].strip('/')

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
        start_response('200 OK',
                       [('Content-Type', 'application/json'),
                        ('Content-Length', str(len(resp)))])
        return [resp]
    except Exception:
        log.exception('')
        resp = 'Internal server error'
        start_response('500 Internal server error',
                       [('Content-Type', 'text/plain'),
                        ('Content-Length', str(len(resp)))])
        return [resp]
