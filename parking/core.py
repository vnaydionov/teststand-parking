# -*- coding: utf-8 -*-

from __future__ import with_statement
import os
import sys
import time
import math
import decimal
import datetime
import random
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from model import Product, Order, Payment, \
        Account, AccountReceipt, AccountConsume, AccountTransfer

api_functions = ('get_service_info', 'create_reservation', 'pay_reservation',
    'cancel_reservation', 'issue_ticket', 'leave_parking',
    'check_plate_number', 'stop_service', 'get_user_account',
    'account_transfer')

log = logging.getLogger('parking.core')

session_maker = None
def new_session():
    global session_maker
    if not session_maker:
        url = None
        if getattr(os, 'environ', None):
            url = os.environ.get('PARKING_DB')
        if not url:
            url = 'mysql://parking_user:parking_pwd@localhost/parking_db'
            if 'PyPy' in sys.version:
                url = 'mysql+pymysql://parking_user:parking_pwd@localhost/parking_db'
            if 'java' in sys.platform.lower():
                url = 'mysql+zxjdbc://parking_user:parking_pwd@localhost/parking_db'
        engine = create_engine(url)
        session_maker = sessionmaker(bind=engine, autocommit=True)
    return session_maker()

def total_seconds(tdelta):
    return int(tdelta.days*3600*24 + tdelta.seconds)

class ApiResult(Exception):
    def __init__(self, resp):
        super(ApiResult, self).__init__()
        self.resp = resp

def api_method_deco_gen(default_error='bad_transaction'):
    def api_method_deco(f):
        def g(**params):
            session = new_session()
            try:
                try:
                    version = int(params.get('version', '0'))
                    assert version in (0, 1, 2)
                except:
                    raise ApiResult(mk_resp('bad_protocol'))
                with session.begin():
                    return f(session, **params)
            except ApiResult, e:
                return e.resp
            except:
                log.exception('')
                return mk_resp(default_error)
        return g
    return api_method_deco

def mk_resp(status, **params):
    params['status'] = status
    params['ts'] = '%.3f' % time.time()
    return params

def round_hours(hours, first_hour=False):
    minutes = int(decimal.Decimal(hours)*60)
    assert minutes >= 0
    if not minutes and first_hour:
        minutes = 1
    minutes = ((minutes + 14) / 15) * 15
    return decimal.Decimal(minutes)/60

def get_parking_from_sd(version, service_descr):
    if not version:
        parking_name = str(service_descr.get('parking_object_id', ''))
    else:
        parking_name = str(service_descr.get('parking_id', ''))
    return parking_name

def get_parking(session, version, service_descr, lock=False):
    parking_name = get_parking_from_sd(version, service_descr)
    if not version:
        assert parking_name != ''
    else:
        if not parking_name:
            raise ApiResult(mk_resp('not_available',
                    status_code='invalid_parking_id'))
    q = session.query(Product)
    if lock:
        q = q.with_lockmode('update')
    parkings = q.filter_by(name=parking_name).all()
    if not version:
        assert len(parkings) == 1
    else:
        if len(parkings) != 1:
            raise ApiResult(mk_resp('not_available',
                    status_code='invalid_parking_id'))
    return parkings[0]

def get_plate_number(version, service_descr, reserve=False):
    plate_number = None
    if not version:
        if 'user_ticket' not in service_descr and reserve:
            plate_number = str(service_descr['plate_number'])
    else:
        plate_number = str(service_descr.get('registration_plate') or '')
        if (version == 1 or reserve) and not plate_number:
            raise ApiResult(mk_resp('not_available',
                    status_code='invalid_registration_plate'))
    return plate_number

def get_hours(version, service_descr):
    if not version:
        hours = decimal.Decimal(service_descr['hours'])
    else:
        duration = int(service_descr.get('duration') or 0)
        if duration <= 0:
            raise ApiResult(mk_resp('not_available',
                    status_code='invalid_duration'))
        hours = decimal.Decimal(duration) / 60
    return hours

def get_order(session, version, service_descr, lock=False):
    orders_q = session.query(Order)
    if lock:
        orders_q = orders_q.with_lockmode('update')
    parking_name = get_parking_from_sd(version, service_descr)
    if parking_name:
        orders_q = orders_q.join(Order.product).filter(
                Product.name == parking_name)
    if 'user_ticket' in service_descr:
        orders = orders_q.filter_by(
                ticket_number=service_descr['user_ticket']).all()
        if not version:
            assert len(orders) == 1
        else:
            if len(orders) != 1:
                raise ApiResult(mk_resp('not_available',
                        status_code='user_ticket_not_found'))
        order = orders[0]
        if not version:
            assert not order.finish_ts
        else:
            if order.finish_ts:
                raise ApiResult(mk_resp('not_available',
                        status_code='user_ticket_out_of_parking'))
    else:
        plate_number = get_plate_number(version, service_descr, reserve=lock)
        orders = orders_q.filter_by(plate_number=plate_number).all()
        if len(orders) != 1:
            order = None
        else:
            order = orders[0]
            if order.finish_ts:
                order = None
    return order

def get_ticket_hours(session, version, user_ticket, lock=False):
    orders_q = session.query(Order)
    if lock:
        orders_q = orders_q.with_lockmode('update')
    orders = orders_q.filter_by(ticket_number=user_ticket).all()
    if not version:
        assert len(orders) == 1
    else:
        if len(orders) != 1:
            raise ApiResult(mk_resp('not_available',
                    status_code='user_ticket_not_found'))
    order = orders[0]
    if not version:
        assert not order.finish_ts
    else:
        if order.finish_ts:
            raise ApiResult(mk_resp('not_available',
                    status_code='user_ticket_out_of_parking'))
    hours = decimal.Decimal(0)
    now = datetime.datetime.now()
    if now > order.paid_until_ts:
        hours = total_seconds(now - order.paid_until_ts)\
            / decimal.Decimal(3600)
    return (order, hours)

def get_hours_and_price(session, version, service_descr, parking, lock=False):
    if 'user_ticket' in service_descr:
        order, hours = get_ticket_hours(session, version,
                service_descr['user_ticket'], lock=lock)
        if not version:
            assert order.product == parking
        else:
            if order.product != parking:
                raise ApiResult(mk_resp('not_available',
                        status_code='user_ticket_not_found'))
        price_per_hour = order.price
        first_hour = order.paid_until_ts == order.start_ts
    else:
        order = None
        first_hour = True
        hours = get_hours(version, service_descr)
        price_per_hour = parking.price
    hours = round_hours(hours, first_hour=first_hour)
    price = hours * price_per_hour
    return (hours, price, order)

def get_account_balance(session, user_id):
    accs = session.query(Account).filter_by(user_eid=user_id).all()
    if len(accs) == 1:
        return accs[0].balance
    return decimal.Decimal(0)

def get_account(session, user_eid):
    accs = session.query(Account).with_lockmode('update')\
            .filter_by(user_eid=user_eid).all()
    assert len(accs) in (0, 1)
    if not accs:
        account = Account(user_eid=user_eid, balance=decimal.Decimal(0),
                reserved=decimal.Decimal(0))
        session.add(account)
        session.flush()
    else:
        account = accs[0]
    return account

def create_account_receipt(session, user_eid, order, amount):
    assert amount <= order.paid_amount
    account = get_account(session, user_eid)
    receipt = AccountReceipt(account=account, src_order=order,
            amount=amount)
    session.add(receipt)
    account.balance += amount
    order.paid_amount -= amount
    now = datetime.datetime.now()
    order.paid_until_ts = now
    session.flush()

def create_account_consume(session, user_eid, payment, amount,
        reserve):
    account = get_account(session, user_eid)
    assert amount <= account.balance - account.reserved
    consume = AccountConsume(account=account, dst_payment=payment,
            amount=amount, is_reserved=int(bool(reserve)))
    session.add(consume)
    if reserve:
        account.reserved += amount
    else:
        account.balance -= amount
    payment.amount += amount
    session.flush()

def fix_consume(session, payment, approve):
    assert len(payment.consumes) == 1
    consume = payment.consumes[0]
    account = consume.account
    session.refresh(account, lockmode='update')
    session.refresh(consume, lockmode='update')
    assert account.reserved >= consume.amount
    account.reserved -= consume.amount
    if approve:
        assert account.balance >= consume.amount
        account.balance -= consume.amount
    else:
        consume.amount = 0;
    consume.is_reserved = 0
    session.flush()

@api_method_deco_gen(default_error='not_available')
def get_service_info(session, version=None, service_descr=None, user_id=None):
    version = int(version or 0)
    if version:
        if user_id is None or user_id == '':
            raise ApiResult(mk_resp('not_available',
                    status_code='invalid_user_id'))
    plate_number = get_plate_number(version, service_descr)
    parking = get_parking(session, version, service_descr)
    (hours, price, order) = get_hours_and_price(session, version,
            service_descr, parking)
    resp = mk_resp('success', price='%.2f' % price,
            info={'available_places': parking.places_avail})
    if version:
        if order:
            resp['info']['start_ts'] = '%.3f' % time.mktime(
                    order.start_ts.timetuple())
        else:
            resp['info']['start_ts'] = '%.3f' % time.mktime(
                    datetime.datetime.now().timetuple())
        resp['info']['duration'] = int('%.0f' % (hours * 60))
        if 'user_ticket' in service_descr and order:
            resp['info']['paid_duration'] = total_seconds(
                    order.paid_until_ts - order.start_ts) / 60
    if version >= 2:
        resp['info']['balance'] = '%.2f' % get_account_balance(session, user_id)
    raise ApiResult(resp)

@api_method_deco_gen(default_error='not_available')
def create_reservation(session, version=None, service_descr=None,
        price=None, transaction_id=None, user_id=None, pay_from_balance=None):
    version = int(version or 0)
    if version:
        if user_id is None or user_id == '':
            raise ApiResult(mk_resp('not_available',
                    status_code='invalid_user_id'))
    plate_number = get_plate_number(version, service_descr, reserve=True)
    parking = get_parking(session, version, service_descr, lock=True)
    price = decimal.Decimal(price)
    if pay_from_balance:
        pay_from_balance = decimal.Decimal(pay_from_balance)
    else:
        pay_from_balance = decimal.Decimal(0)
    if pay_from_balance < decimal.Decimal(0) or pay_from_balance > price:
        raise ApiResult(mk_resp('wrong_price'))
    if transaction_id in (None, '') or len(str(transaction_id)) > 64 \
            or len(str(transaction_id)) < 4:
        raise ApiResult(mk_resp('bad_transaction'))
    payments = session.query(Payment).with_lockmode('update')\
            .filter_by(trans_number=str(transaction_id)).all()
    if payments:
        if len(payments) != 1:
            raise ApiResult(mk_resp('bad_transaction'))
        payment = payments[0]
        # only basic checks here
        if payment.amount == price and payment.order.product == parking:
            raise ApiResult(mk_resp('success'))
        raise ApiResult(mk_resp('bad_transaction'))
    (hours, amount, order) = get_hours_and_price(session, version,
            service_descr, parking, lock=True)
    if price != amount:
        raise ApiResult(mk_resp('wrong_price'))
    if not parking.places_avail:
        raise ApiResult(mk_resp('not_available'))
    now = datetime.datetime.now()
    if not order:
        order = Order(product=parking, user_eid=user_id,
                plate_number=plate_number, start_ts=now,
                paid_amount=0, paid_until_ts=now)
        session.add(order)
    payment = Payment(trans_number=str(transaction_id),
            hours=hours, order=order, amount=amount - pay_from_balance,
            ts=now)
    session.add(payment)
    if pay_from_balance:
        create_account_consume(session, user_id, payment,
                pay_from_balance, reserve=True)
    resp = mk_resp('success')
    if version:
        resp['price'] = '%.2f' % amount
        resp['info'] = {}
        resp['info']['start_ts'] = '%.3f' % time.mktime(
                order.start_ts.timetuple())
        resp['info']['duration'] = int('%.0f' % (hours * 60))
        if 'user_ticket' in service_descr:
            resp['info']['paid_duration'] = 0  # TODO: support additional payments
    return resp

@api_method_deco_gen(default_error='bad_transaction')
def pay_reservation(session, version=None, transaction_id=None):
    payment = session.query(Payment).with_lockmode('update')\
            .filter_by(trans_number=str(transaction_id)).one()
    if payment.payment_ts:
        raise ApiResult(mk_resp('success'))
    if payment.cancel_ts:
        raise ApiResult(mk_resp('bad_transaction'))
    order = session.query(Order).with_lockmode('update')\
            .filter_by(id=payment.order_id).one()
    now = datetime.datetime.now()
    payment.payment_ts = now
    payment.order.paid_amount += payment.amount
    payment.order.paid_until_ts += datetime.timedelta(
            seconds=int(payment.hours * 3600))
    if not order.ticket_number and now < order.paid_until_ts:
        session.refresh(order.product, lockmode='update')
        order.product.places_avail -= 1
    if payment.consumes:
        fix_consume(session, payment, approve=True)
    return mk_resp('success')

@api_method_deco_gen(default_error='bad_transaction')
def cancel_reservation(session, version=None, transaction_id=None):
    payment = session.query(Payment).with_lockmode('update')\
            .filter_by(trans_number=str(transaction_id)).one()
    if payment.cancel_ts:
        raise ApiResult(mk_resp('success'))
    order = session.query(Order).with_lockmode('update')\
            .filter_by(id=payment.order_id).one()
    now = datetime.datetime.now()
    payment.cancel_ts = now
    if payment.payment_ts:
        payment.order.paid_amount -= payment.amount
        payment.order.paid_until_ts -= datetime.timedelta(
                seconds=int(payment.hours * 3600))
        if not order.ticket_number and now >= order.paid_until_ts:
            order.finish_ts = now
            session.refresh(order.product, lockmode='update')
            order.product.places_avail += 1
    else:
        order.finish_ts = now
    if payment.consumes:
        fix_consume(session, payment, approve=False)
    return mk_resp('success')

@api_method_deco_gen(default_error='bad_transaction')
def stop_service(session, version=None, transaction_id=None):
    payment = session.query(Payment).with_lockmode('update')\
            .filter_by(trans_number=str(transaction_id)).one()
    assert payment.payment_ts and not payment.cancel_ts
    order = session.query(Order).with_lockmode('update')\
            .filter_by(id=payment.order_id).one()
    assert not order.ticket_number
    existing = session.query(AccountReceipt).filter_by(
            src_order_id=order.id).all()
    if existing:
        assert len(existing) == 1
        return mk_resp('success', delta_amount='%.2f' % existing[0].amount)
    now = datetime.datetime.now()
    if now >= order.paid_until_ts:
        return mk_resp('success', delta_amount='0.00')
    total_secs_left = total_seconds(order.paid_until_ts - now) - 1
    duration_left = (total_secs_left / (15 * 60)) * 15 # rounded minutes
    price_per_minute = order.paid_amount / (total_seconds(
            order.paid_until_ts - order.start_ts) / 60)
    user_eid = order.user_eid
    delta_amount = (duration_left * price_per_minute).quantize(
            decimal.Decimal('.01'))
    log.debug('total_seconds_left=%d duration_left=%d price=%.2f delta=%.2f' % (
        total_secs_left, duration_left, price_per_minute, delta_amount))
    create_account_receipt(session, user_eid, order, delta_amount)
    return mk_resp('success', delta_amount='%.2f' % delta_amount)

@api_method_deco_gen(default_error='bad_transaction')
def get_user_account(session, version=None, user_id=None):
    return mk_resp('success', balance='%.2f' % get_account_balance(session, user_id))

@api_method_deco_gen(default_error='bad_transaction')
def account_transfer(session, version=None, transaction_id=None,
        src_user_id=None, dst_user_id=None):
    src_account = get_account(session, src_user_id)
    dst_account = get_account(session, dst_user_id)
    if src_account == dst_account:
        raise ApiResult(mk_resp('bad_transaction',
                status_code='same_src_and_dst'))
    existing_transfers = session.query(AccountTransfer)\
            .with_lockmode('update')\
            .filter(AccountTransfer.trans_number == transaction_id).all()
    if len(existing_transfers):
        existing_transfer = existing_transfers[0]
        if existing_transfer.src_account != src_account \
                or existing_transfer.dst_account != dst_account:
            raise ApiResult(mk_resp('bad_transaction',
                    status_code='another_trans_exists'))
        raise ApiResult(mk_resp('success', status_code='already_done'))
    if src_account.balance <= 0:
        raise ApiResult(mk_resp('success',
                status_code='nothing_to_transfer'))
    if src_account.reserved != 0:
        raise ApiResult(mk_resp('not_available',
                status_code='reserved_funds_present'))
    amount = src_account.balance
    trans = AccountTransfer(ts=datetime.datetime.now(),
            trans_number=transaction_id,
            src_account=src_account, dst_account=dst_account, amount=amount)
    session.add(trans)
    src_account.balance -= amount
    dst_account.balance += amount
    return mk_resp('success')

@api_method_deco_gen(default_error='not_available')
def issue_ticket(session, version=None, parking_id=None):
    parking_name = str(parking_id or '')
    assert parking_name
    parking = session.query(Product).with_lockmode('update')\
            .filter_by(name=parking_name).one()
    assert parking.places_avail > 0
    while True:
        ticket_number = str(random.randint(1000000000, 1999999999))
        if not session.query(Order).filter_by(ticket_number=ticket_number).count():
            break
    now = datetime.datetime.now()
    order = Order(product=parking, ticket_number=ticket_number,
            start_ts=now, paid_until_ts=now, price=parking.price, paid_amount=0)
    parking.places_avail -= 1
    session.add(order)
    return mk_resp('success', user_ticket=ticket_number,
            available_places=parking.places_avail)

@api_method_deco_gen(default_error='not_available')
def leave_parking(session, version=None, parking_id=None, user_ticket=None):
    now = datetime.datetime.now()
    parking = session.query(Product)\
            .filter_by(name=parking_id).one()
    orders = session.query(Order).with_lockmode('update').filter(
            (Order.ticket_number == user_ticket) &
            (Order.product == parking) &
            (Order.finish_ts == None)).all()
    assert len(orders) == 1
    order = orders[0]
    if order.start_ts == order.paid_until_ts or \
            now >= order.paid_until_ts + datetime.timedelta(minutes=15):
        raise ApiResult(mk_resp('not_enough_paid'))
    order.finish_ts = now
    session.refresh(parking, lockmode='update')
    parking.places_avail += 1
    return mk_resp('success')

@api_method_deco_gen(default_error='not_available')
def check_plate_number(session, version=None, registration_plate=None):
    plate_number = str(registration_plate or '')
    assert plate_number
    active_orders_count = session.query(Order).filter(
            (Order.plate_number == str(plate_number)) &
            (Order.paid_until_ts > datetime.datetime.now()) &
            (Order.finish_ts == None)).count()
    if active_orders_count >= 1:
        raise ApiResult(mk_resp('success', paid='true'))
    raise ApiResult(mk_resp('success', paid='false'))

