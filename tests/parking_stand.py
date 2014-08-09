import urllib
import json
import decimal
import logging

from http_util import split_url, http_post

log = logging.getLogger('parking_stand')

class ParkingStand(object):
    def __init__(self, url, timeout, version=None):
        self.url = url
        self.timeout = timeout
        self.url_parts = split_url(self.url)
        self.version = int(version or 0)

    def _fmt_service_descr(self, service_descr):
        return '{%s}' % (', '.join('"%s": "%s"' % (k, v)
                for k, v in service_descr.iteritems()))

    def _call_method(self, method, params):
        try:
            if self.version > 0:
                params = params + [('version', self.version)]
            (code, desc, body) = http_post(self.url_parts, params=params,
                    method='GET', path_add=method, timeout=self.timeout)
        except Exception, e:
            log.exception('')
            return {'method': 'ParkingStand.%s' % method,
                    'status': 'error',
                    'status_desc': 'network error: %s(%s)' % (
                        e.__class__.__name__, str(e))}
        if code != 200:
            return {'method': 'ParkingStand.%s' % method,
                    'status': 'error',
                    'status_desc': 'http error: %s: %s' % (code, desc)}
        try:
            parsed_body = json.loads(body)
        except ValueError, e:
            return {'method': 'ParkingStand.%s' % method,
                    'status': 'error',
                    'status_desc': 'JSON parsing error'}
        if not isinstance(parsed_body, dict) or \
                'status' not in parsed_body.keys() or \
                'ts' not in parsed_body.keys():
            return {'method': 'ParkingStand.%s' % method,
                    'status': 'error',
                    'status_desc': 'invalid response structure'}
        if 'price' in parsed_body.keys():
            parsed_body['price'] = decimal.Decimal('%.2f' %
                    decimal.Decimal(parsed_body['price']))
        return parsed_body

    def get_service_info(self, service_descr, user_id):
        params = [('service_descr', self._fmt_service_descr(service_descr))]
        if user_id is not None and user_id != '':
            params.append(('user_id', str(user_id)))
        resp = self._call_method('get_service_info', params)
        return resp

    def create_reservation(self, service_descr, price, transaction_id, user_id,
            pay_from_balance=0):
        params = [('service_descr', self._fmt_service_descr(service_descr)),
                 #('price', '%.2f' % price),
                 ('price', '%.0f' % price),
                 ('transaction_id', str(transaction_id))]
        if user_id is not None and user_id != '':
            params.append(('user_id', str(user_id)))
        if self.version >= 2 or pay_from_balance:
            params.append(('pay_from_balance',
                '%.2f' % decimal.Decimal(pay_from_balance)))
        return self._call_method('create_reservation', params)

    def pay_reservation(self, transaction_id):
        return self._call_method('pay_reservation',
                [('transaction_id', str(transaction_id))])

    def cancel_reservation(self, transaction_id):
        return self._call_method('cancel_reservation',
                [('transaction_id', str(transaction_id))])

    def stop_service(self, transaction_id):
        return self._call_method('stop_service',
                [('transaction_id', str(transaction_id))])

    def get_user_account(self, user_id):
        return self._call_method('get_user_account',
                [('user_id', str(user_id))])

    def account_transfer(self, transaction_id, src_user_id, dst_user_id):
        params = [('transaction_id', str(transaction_id)),
                  ('src_user_id', str(src_user_id)),
                  ('dst_user_id', str(dst_user_id))]
        return self._call_method('account_transfer', params)

    def issue_ticket(self, parking_id):
        return self._call_method('issue_ticket',
                [('parking_id', str(parking_id))])

    def leave_parking(self, parking_id, user_ticket):
        return self._call_method('leave_parking',
                [('parking_id', str(parking_id)),
                 ('user_ticket', str(user_ticket))])

    def check_plate_number(self, registration_plate):
        return self._call_method('check_plate_number',
                [('registration_plate', str(registration_plate))])

