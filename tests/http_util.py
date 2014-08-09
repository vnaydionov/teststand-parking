import logging
import socket
import urllib
import httplib
import sys

log = logging.getLogger('http_post')

def dbg(s):
    log.debug(s)

def params2str(params, mask_params=None, obfuscate_params=None, enc='utf-8'):
    mask_params = mask_params or ()
    obfuscate_params = obfuscate_params or {}
    filtered = ((p, q if p not in mask_params else 'XXX') for p, q in params)
    filtered = ((p, q if p not in obfuscate_params
        else obfuscate_params[p](q)) for p, q in filtered)
    return urllib.urlencode(tuple((unicode(k).encode(enc), unicode(v).encode(enc))
                                  for k, v in filtered))

def split_url(url):
    proto = url.split('://')[0].lower()
    port = 80
    if proto == 'https':
        port = 443
    (host, path) = urllib.splithost('//' + url.split('//')[1])
    if ':' in host:
        host_parts = host.split(':')
        port_str = host_parts[-1]
        if port_str.isdigit():
            port = int(port_str)
            host = ':'.join(host_parts[:-1])
    return (proto, host, port, path)

if sys.version_info >= (2,6):
    HTTPConnection = httplib.HTTPConnection
    HTTPSConnection = httplib.HTTPSConnection
else:
    class HTTPConnection(httplib.HTTPConnection):
        def __init__(self, host, port=None, strict=None, timeout=None):
            httplib.HTTPConnection.__init__(self, host, port, strict)
            self.timeout = timeout
    
        def connect(self):
            """Connect to the host and port specified in __init__."""
            msg = "getaddrinfo returns an empty list"
            for res in socket.getaddrinfo(self.host, self.port, 0,
                                          socket.SOCK_STREAM):
                af, socktype, proto, canonname, sa = res
                try:
                    self.sock = socket.socket(af, socktype, proto)
                    if self.timeout:
                        self.sock.settimeout(self.timeout)
                    if self.debuglevel > 0:
                        print "connect: (%s, %s)" % (self.host, self.port)
                    self.sock.connect(sa)
                except socket.error, msg:
                    if self.debuglevel > 0:
                        print 'connect fail:', (self.host, self.port)
                    if self.sock:
                        self.sock.close()
                    self.sock = None
                    continue
                break
            if not self.sock:
                raise socket.error, msg
    
    class HTTPSConnection(httplib.HTTPSConnection):
        def __init__(self, host, port=None, key_file=None, cert_file=None,
                     strict=None, timeout=None):
            httplib.HTTPSConnection.__init__(
                self, host, port, key_file, cert_file, strict)
            self.timeout = timeout
    
        def connect(self):
            "Connect to a host on a given (SSL) port."
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.timeout:
                sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            ssl = socket.ssl(sock, self.key_file, self.cert_file)
            self.sock = httplib.FakeSocket(sock, ssl)

def http_post(url_parts, params, timeout=None,
              key_file=None, cert_file=None, path_add='',
              mask_params=None, obfuscate_params=None,
              user_headers=None, return_headers=False, method='POST',
              body=None, enc='utf-8'):
    (proto, host, port, path) = url_parts
    path += path_add
    params_str = params2str(params, enc=enc)
    params_dump = params2str(params, mask_params=mask_params,
            obfuscate_params=obfuscate_params, enc=enc)
    dbg('sending %s request to [%s]://[%s]:[%d][%s]: %s' %
            (method, proto, host, port, path, params_dump))
    if method == 'POST':
        if not body:
            body = params_str
    else:
        if params_str:
            path += '?' + params_str
        body = ''
    if proto == 'https':
        conn = HTTPSConnection(host, port, timeout=timeout,
                key_file=key_file, cert_file=cert_file)
    else:
        conn = HTTPConnection(host, port, timeout=timeout)
    headers = {'Accept': '*/*', 'Host': host}
    if method == 'POST':
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        if enc != 'utf-8':
            headers['Content-Type'] += '; charset=%s' % enc
    if user_headers:
        for k, v in user_headers:
            headers[k] = urllib.quote(v, ' /')
        dbg('headers: %s' % repr(headers))
    try:
        conn.request(method, path, body, headers)
        response = conn.getresponse()
        headers = response.getheaders()
        data = response.read()
        conn.close()
        if return_headers:
            dbg('response headers: %s' % repr(headers))
        dbg('response: %d %s' % (response.status, data))
        if return_headers:
            return (response.status, response.reason, data, headers)
        return (response.status, response.reason, data)
    except socket.error, e:
        dbg('socket error: %s' % e)
        raise
