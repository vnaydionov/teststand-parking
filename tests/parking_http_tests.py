# -*- coding: utf-8 -*-

from __future__ import with_statement
import sys
import os
import copy
import random
import time
import hashlib
import logging
from decimal import Decimal
import unittest
import optparse

from parking_stand import ParkingStand

class TestParkingHTTP(unittest.TestCase):
    target_version = None
    user_ticket = None
    stand_uri = None
    check_plate = None
    check_avail = None
    check_status_code = None
    fake_stand = None

    @classmethod
    def print_settings(cls):
        print 'target_version:      %d' % cls.target_version
        print 'user_ticket:         %s' % cls.user_ticket
        print 'stand_uri:           %s' % cls.stand_uri
        print 'check_plate:         %d' % cls.check_plate
        print 'check_avail:         %d' % cls.check_avail
        print 'check_status_code:   %d' % cls.check_status_code
        print 'fake_stand           %d' % cls.fake_stand

    def setUp(self):
        super(TestParkingHTTP, self).setUp()
        self.delay = 15
        self.iface = ParkingStand(self.stand_uri, self.delay,
                version=self.target_version)
        self.logger = logging.getLogger('comment')

    def random_id(self):
        return str(random.randint(0, 2**31 - 1))

    def random_plate(self):
        letters = 'ABEKMHOPCTYX'
        regions = range(1, 200) + [777]
        def rand_letter(): return letters[random.randint(0, len(letters) - 1)]
        return '%s%03d%s%s%02d' % (rand_letter(),
                random.randint(1, 999), rand_letter(), rand_letter(),
                regions[random.randint(0, len(regions) - 1)])

    def get_avail_price(self, service_descr, user_id, parking_account=False):
        resp = self.iface.get_service_info(service_descr=service_descr,
                user_id=user_id)
        self.assertEqual('success', resp['status'])
        if self.target_version > 0:
            self.assert_('start_ts' in resp['info'])
            self.assert_('duration' in resp['info'])
            if 'user_ticket' in service_descr:
                self.assert_('paid_duration' in resp['info'])
        places, price, account = (int(resp['info']['available_places']),
            Decimal(resp['price']), resp['info'].get('balance'))
        if account is not None:
            account = Decimal(account)
        if parking_account:
            return (places, price, account)
        return (places, price)

    def mk_service_descr(self, parking_id=None, registration_plate=None,
            duration=None, start_ts=None, user_ticket=None, version=None):
        version = version
        if version is None:
            version = self.target_version
        serv_descr = {}
        if parking_id is not None:
            if version == 0:
                serv_descr['parking_object_id'] = parking_id
            else:
                serv_descr['parking_id'] = parking_id
        if registration_plate is not None:
            if version == 0:
                serv_descr['plate_number'] = registration_plate
            else:
                serv_descr['registration_plate'] = registration_plate
        if duration is not None:
            if version == 0:
                serv_descr['hours'] = (int(duration) + 59) / 60
            else:
                serv_descr['duration'] = int(duration)
        if start_ts is not None:
            serv_descr['start_ts'] = start_ts
        if user_ticket is not None:
            serv_descr['user_ticket'] = user_ticket
        return serv_descr

    def pay_trans(self, trans):
        log = self.logger
        log.debug(u'Оплачиваю')
        t0 = time.time()
        status = None
        while time.time() - t0 < self.delay:
            r = self.iface.pay_reservation(transaction_id=trans)
            status = r['status']
            log.debug(u'Статус: %s' % status)
            if status == 'success':
                break
            self.assert_(self.target_version == 0 or status == 'in_progress')
            time.sleep(0.5)
        self.assertEqual('success', status)

    def cancel_trans(self, trans):
        log = self.logger
        log.debug(u'Отменяю')
        t0 = time.time()
        status = None
        while time.time() - t0 < self.delay:
            r = self.iface.cancel_reservation(transaction_id=trans)
            status = r['status']
            log.debug(u'Статус: %s' % status)
            if status == 'success':
                break
            self.assert_(self.target_version == 0 or status == 'in_progress')
            time.sleep(0.5)
        self.assertEqual('success', status)

    def test_version(self):
        log = self.logger
        log.debug(u'===Проверка версии протокола===')
        parking_id = '1333'
        hours = 2
        registration_plate = self.random_plate()
        user_id = self.random_id()

        supported = []
        for ver in range(3):
            log.debug(u'Проверяю поддержку версии %d' % ver)
            test_iface = ParkingStand(self.iface.url, self.iface.timeout,
                    version=ver)
            r = test_iface.get_service_info(self.mk_service_descr(
                    parking_id=parking_id, duration=hours*60,
                    registration_plate=registration_plate, version=ver),
                    user_id=user_id)
            log.debug(u'Статус: %s' % r['status'])
            if r['status'] == 'success':
                supported.append(ver)
        log.debug(u'Поддерживаемые версии: %s' % repr(supported))
        self.assert_(self.target_version in supported)

    def test_account_transfer(self):
        log = self.logger
        log.debug(u'===Тестирую перенос между парковочными счетами===')
        parking_id = '1333'
        user_id = self.random_id()

        # Get service info and empty balance of the parking account
        log.debug(u'Получаю цену с предоплатной парковки')
        hours = 2
        registration_plate = self.random_plate()
        service_descr = self.mk_service_descr(
                parking_id=parking_id, duration=hours*60,
                registration_plate=registration_plate)
        (avail_places, price, parking_account) = self.get_avail_price(
                service_descr, user_id, parking_account=True)

        # Create a pre-paid transaction and pay it
        trans = self.random_id()
        log.debug(u'Создаю и оплачиваю транзакцию')
        r = self.iface.create_reservation(service_descr=service_descr,
                transaction_id=trans, price=price, user_id=user_id)
        log.debug(u'Статус: %s' % r['status'])
        self.assertEqual('success', r['status'])
        self.pay_trans(trans)

        # Stop service and put unused funds to the parking account
        log.debug(u'Пополнение парковочного счета')
        r = self.iface.stop_service(transaction_id=trans)
        self.assertEqual('success', r['status'])
        delta_amount = Decimal(r['delta_amount'])

        # Check another user's account directly
        user2_id = self.random_id()
        log.debug(u'Получаю баланс парковочного счета для другого пользователя')
        r = self.iface.get_user_account(user_id=user2_id)
        self.assertEqual('success', r['status'])
        self.assertEqual(Decimal(0), Decimal(r['balance']))

        transaction_id = hashlib.md5('%s;%s;%d' % (user_id, user2_id,
                time.time())).hexdigest()

        # Check possible status_codes: nothing to transfer
        log.debug(u'Выполняю перенос: нечего переносить')
        r = self.iface.account_transfer(transaction_id=transaction_id,
                src_user_id=user2_id, dst_user_id=user_id)
        self.assertEqual('success', r['status'])
        self.assertEqual('nothing_to_transfer', r['status_code'])

        # Check possible status_codes: the same accounts
        log.debug(u'Выполняю перенос: один и тот же счет')
        r = self.iface.account_transfer(transaction_id=transaction_id,
                src_user_id=user_id, dst_user_id=user_id)
        self.assertEqual('bad_transaction', r['status'])
        self.assertEqual('same_src_and_dst', r['status_code'])

        # Reserve funds on account: transfer must fail
        (avail_places, price, parking_account) = self.get_avail_price(
                service_descr, user_id, parking_account=True)
        trans2_id = self.random_id()
        log.debug(u'Резервирую деньги для оплаты с парковочного счета')
        r = self.iface.create_reservation(service_descr=service_descr,
                transaction_id=trans2_id, price=price, user_id=user_id,
                pay_from_balance=min(price, delta_amount))
        self.assertEqual('success', r['status'])

        # Check possible status_codes: the same accounts
        log.debug(u'Выполняю перенос: нельзя, так как есть резерв')
        r = self.iface.account_transfer(transaction_id=transaction_id,
                src_user_id=user_id, dst_user_id=user2_id)
        self.assertEqual('not_available', r['status'])
        self.assertEqual('reserved_funds_present', r['status_code'])

        # Cancel the reservation
        log.debug(u'Отменяю резерв')
        self.cancel_trans(trans2_id)

        # Perform the transfer
        log.debug(u'Выполняю перенос')
        t0 = time.time()
        while 1:
            r = self.iface.account_transfer(transaction_id=transaction_id,
                    src_user_id=user_id, dst_user_id=user2_id)
            self.assert_(r['status'] in ('success', 'in_progress'))
            if r['status'] == 'success':
                break
            self.assert_(time.time() - t0 < 10)

        log.debug(u'Пробую еще раз с теми же параметрами')
        r = self.iface.account_transfer(transaction_id=transaction_id,
                src_user_id=user_id, dst_user_id=user2_id)
        self.assertEqual('success', r['status'])
        self.assertEqual('already_done', r['status_code'])

        # Check possible status_codes: existing transaction
        log.debug(u'Выполняю перенос: существующая транзакция')
        user3_id = self.random_id()
        r = self.iface.account_transfer(transaction_id=transaction_id,
                src_user_id=user_id, dst_user_id=user3_id)
        self.assertEqual('bad_transaction', r['status'])
        self.assertEqual('another_trans_exists', r['status_code'])

        # Check another user's account again
        log.debug(u'Получаю баланс счета другого пользователя, еще раз')
        r = self.iface.get_user_account(user_id=user2_id)
        self.assertEqual('success', r['status'])
        self.assertEqual(delta_amount, Decimal(r['balance']))

        # Check original user's account again
        log.debug(u'Получаю баланс счета исходного пользователя')
        r = self.iface.get_user_account(user_id=user_id)
        self.assertEqual('success', r['status'])
        self.assertEqual(Decimal(0), Decimal(r['balance']))

    def test_parking_account(self):
        log = self.logger
        log.debug(u'===Тестирую парковочный счет===')
        parking_id = '1333'
        user_id = self.random_id()

        account_balance = Decimal(0)

        # Check user account directly
        log.debug(u'Получаю баланс парковочного счета напрямую')
        r = self.iface.get_user_account(user_id=user_id)
        self.assertEqual('success', r['status'])
        self.assertEqual(account_balance, Decimal(r['balance']))

        for i in (1, 2):
            # Get service info and empty balance of the parking account
            log.debug(u'Получаю цену с предоплатной парковки')
            hours = 2
            registration_plate = self.random_plate()
            service_descr = self.mk_service_descr(
                    parking_id=parking_id, duration=hours*60,
                    registration_plate=registration_plate)
            (avail_places, price, parking_account) = self.get_avail_price(
                    service_descr, user_id, parking_account=True)
            log.debug(u'Проверяем, что счет не изменился')
            self.assertEqual(account_balance, parking_account)

            # Create a pre-paid transaction and pay it
            trans = self.random_id()
            log.debug(u'Создаю и оплачиваю транзакцию')
            r = self.iface.create_reservation(service_descr=service_descr,
                    transaction_id=trans, price=price, user_id=user_id)
            log.debug(u'Статус: %s' % r['status'])
            self.assertEqual('success', r['status'])
            self.pay_trans(trans)

            # Stop service and put unused funds to the parking account
            log.debug(u'Пополнение парковочного счета #%d' % i)
            r = self.iface.stop_service(transaction_id=trans)
            self.assertEqual('success', r['status'])
            delta_amount = Decimal(r['delta_amount'])
            account_balance += delta_amount

            # Ensure that calling this twice does not change balance twice
            log.debug(u'Пополнение парковочного счета #%d (вторая попытка)' % i)
            r = self.iface.stop_service(transaction_id=trans)
            self.assertEqual('success', r['status'])
            delta_amount2 = Decimal(r['delta_amount'])
            self.assertEqual(delta_amount, delta_amount2)

            # Check the balance must not be empty
            hours_left = hours - Decimal(15)/Decimal(60)
            self.assertEqual(Decimal('1.75'), hours_left)
            log.debug(u'Получаю цену с предоплатной парковки и баланс')
            hours = 1
            registration_plate = self.random_plate()
            service_descr = self.mk_service_descr(
                    parking_id=parking_id, duration=hours*60,
                    registration_plate=registration_plate)
            (avail_places, price, parking_account) = self.get_avail_price(
                    service_descr, user_id, parking_account=True)
            log.debug(u'Проверяем, что счет не пуст (15 минут квант)')
            expected_delta = (hours_left * price / hours).quantize(Decimal('.01'))
            self.assertEqual(expected_delta, delta_amount)
            self.assertEqual(account_balance, parking_account)

            # Check user account directly
            log.debug(u'Получаю баланс парковочного счета напрямую')
            r = self.iface.get_user_account(user_id=user_id)
            self.assertEqual('success', r['status'])
            self.assertEqual(account_balance, Decimal(r['balance']))

        # Now try to use the balance to pay for the service
        log.debug(u'Создаю и оплачиваю с баланса транзакцию')
        trans = self.random_id()
        r = self.iface.create_reservation(service_descr=service_descr,
                transaction_id=trans, price=price, user_id=user_id,
                pay_from_balance=price)
        log.debug(u'Статус: %s' % r['status'])
        self.assertEqual('success', r['status'])
        self.pay_trans(trans)
        price0 = price

        # Check the balance - it must be empty
        log.debug(u'Получаю цену с предоплатной парковки и баланс')
        hours = 1
        registration_plate = self.random_plate()
        service_descr = self.mk_service_descr(
                parking_id=parking_id, duration=hours*60,
                registration_plate=registration_plate)
        (avail_places, price, parking_account_new) = self.get_avail_price(
                service_descr, user_id, parking_account=True)
        log.debug(u'Проверяем, что счет уменьшился (15 минут квант)')
        self.assertEqual(price0, parking_account - parking_account_new)

        # Stop service and return unused funds to the parking account
        log.debug(u'Возврат на парковочный счет')
        r = self.iface.stop_service(transaction_id=trans)
        self.assertEqual('success', r['status'])
        delta_amount = Decimal(r['delta_amount'])
        self.assert_(delta_amount > 0)
        r = self.iface.get_user_account(user_id=user_id)
        self.assertEqual('success', r['status'])
        self.assertEqual(parking_account_new + delta_amount,
                Decimal(r['balance']))

    def test_prepay(self):
        log = self.logger
        log.debug(u'===Тестирую предоплатную схему===')
        parking_id = '1333'
        hours = 2
        trans = self.random_id()
        registration_plate = self.random_plate()
        user_id = None
        if self.target_version > 0:
            user_id = self.random_id()

        if self.target_version > 0:
            # Get service info by wrong params: no user_id
            log.debug(u'Получаю цену без user_id')
            r = self.iface.get_service_info(self.mk_service_descr(
                    parking_id=parking_id, duration=hours*60,
                    registration_plate=registration_plate), user_id=None)
            log.debug(u'Статус: %s' % r['status'])
            self.assertEqual('not_available', r['status'])
            if self.check_status_code:
                self.assertEqual('invalid_user_id', r['status_code'])

        # Get service info by wrong params: wrong parking_id
        log.debug(u'Получаю цену с неверным parking_id')
        r = self.iface.get_service_info(self.mk_service_descr(
                parking_id='1333-', duration=hours*60,
                registration_plate=registration_plate), user_id=user_id)
        log.debug(u'Статус: %s' % r['status'])
        self.assertEqual('not_available', r['status'])
        if self.target_version > 0:
            if self.check_status_code:
                self.assertEqual('invalid_parking_id', r['status_code'])

        # Get service info by wrong params: no duration given
        log.debug(u'Получаю цену без указания часов')
        r = self.iface.get_service_info(self.mk_service_descr(
                parking_id=parking_id,
                registration_plate=registration_plate), user_id=user_id)
        log.debug(u'Статус: %s' % r['status'])
        self.assertEqual('not_available', r['status'])
        if self.target_version > 0:
            if self.check_status_code:
                self.assertEqual('invalid_duration', r['status_code'])

        if self.target_version == 1:
            # Get service info by wrong params: no registration_plate
            log.debug(u'Получаю цену без указания номера авто')
            r = self.iface.get_service_info(self.mk_service_descr(
                    parking_id=parking_id, duration=hours*60), user_id=user_id)
            log.debug(u'Статус: %s' % r['status'])
            self.assertEqual('not_available', r['status'])
            if self.check_status_code:
                self.assertEqual('invalid_registration_plate', r['status_code'])

        # Get service info by valid params
        log.debug(u'Получаю цену с верными параметрами')
        service_descr = self.mk_service_descr(
                parking_id=parking_id, duration=hours*60,
                registration_plate=registration_plate)
        (avail_places, price) = self.get_avail_price(service_descr, user_id)

        # Create transaction with no registration_plate
        service_descr0 = self.mk_service_descr(
                parking_id=parking_id, duration=hours*60)
        log.debug(u'Резервирую цену без номера авто')
        r = self.iface.create_reservation(service_descr=service_descr0,
                transaction_id=trans, price=price, user_id=user_id)
        log.debug(u'Статус: %s' % r['status'])
        self.assertEqual('not_available', r['status'])
        if self.target_version > 0:
            if self.check_status_code:
                self.assertEqual('invalid_registration_plate', r['status_code'])

        # Create transaction with wrong price
        log.debug(u'Создаю транзакцию с неверной ценой')
        r = self.iface.create_reservation(service_descr=service_descr,
                transaction_id=trans, price=price + 1, user_id=user_id)
        log.debug(u'Статус: %s' % r['status'])
        self.assertEqual('wrong_price', r['status'])

        # Create transaction with proper price
        log.debug(u'Создаю транзакцию с верными данными')
        r = self.iface.create_reservation(service_descr=service_descr,
                transaction_id=trans, price=price, user_id=user_id)
        log.debug(u'Статус: %s' % r['status'])
        self.assertEqual('success', r['status'])

        # Repeat it twice
        log.debug(u'Пытаюсь повторно создать транзакцию')
        r = self.iface.create_reservation(service_descr=service_descr,
                transaction_id=trans, price=price, user_id=user_id)
        log.debug(u'Статус: %s' % r['status'])
        self.assertEqual('success', r['status'])

        if self.check_plate:
            # Reservation created, but not paid
            log.debug(u'Проверяю, что транзакция еще не оплачена')
            r = self.iface.check_plate_number(registration_plate=registration_plate)
            self.assertEqual('success', r['status'])
            self.assertEqual('false', r['paid'])

        # Pay
        self.pay_trans(trans)

        if self.check_avail:
            # Available places decrement.
            r = self.iface.get_service_info(service_descr=service_descr,
                    user_id=user_id)
            new_avail_places = r['info']['available_places']
            self.assertEqual(avail_places - 1, new_avail_places)

        if self.check_plate:
            # Reservation created, paid
            log.debug(u'Проверяю, что транзакция оплачена')
            r = self.iface.check_plate_number(registration_plate=registration_plate)
            self.assertEqual('success', r['status'])
            self.assertEqual('true', r['paid'])

        # Cancel reservation
        self.cancel_trans(trans)

        if self.check_plate:
            # Reservation created, not paid
            log.debug(u'Проверяю, что транзакция сменила статус на неоплачено')
            r = self.iface.check_plate_number(registration_plate=registration_plate)
            self.assertEqual('success', r['status'])
            self.assertEqual('false', r['paid'])

        if self.check_avail:
            # Check available places inc
            r  = self.iface.get_service_info(service_descr=service_descr,
                    user_id=user_id)
            new_avail_places = r['info']['available_places']
            self.assertEqual(avail_places, new_avail_places)

        # And get it twice :)
        log.debug(u'Повторная оплата')
        self.pay_trans(trans)
        
        log.debug(u'Отмена транзакции')
        self.cancel_trans(trans)

    def test_postpay(self):
        log = self.logger
        log.debug(u'===Тестирую постоплатную схему===')
        parking_id = '15001'
        if self.user_ticket == 'random':
            parking_id = '13333'
        registration_plate = self.random_plate()
        user_id = None
        if self.target_version > 0:
            user_id = self.random_id()

        # Generate ticket for parking object
        # Avail places will decrement
        if not self.user_ticket:
            r = self.iface.issue_ticket(parking_id=parking_id)
            self.assertEqual('success', r['status'])
            user_ticket = r['user_ticket']
            avail_places0 = int(r['available_places']) + 1
        elif self.user_ticket == 'random':
            while 1:
                user_ticket = self.random_id()
                last_digit = user_ticket[-1]
                if last_digit not in ('0', '5'):
                    break
        else:
            user_ticket = self.user_ticket

        if self.target_version > 0:
            # Get service info by wrong params: bad user_ticket
            log.debug(u'Получаю цену для неправильного тикета')
            r = self.iface.get_service_info(self.mk_service_descr(
                    parking_id=parking_id, user_ticket='xxx0',
                    registration_plate=registration_plate), user_id=user_id)
            log.debug(u'Статус: %s' % r['status'])
            self.assertEqual('not_available', r['status'])
            if self.check_status_code:
                self.assertEqual('user_ticket_not_found', r['status_code'])

        if self.target_version == 1:
            # Get service info by wrong params: no registration_plate
            log.debug(u'Получаю цену без указания номера авто')
            r = self.iface.get_service_info(self.mk_service_descr(
                    parking_id=parking_id, user_ticket=user_ticket),
                    user_id=user_id)
            log.debug(u'Статус: %s' % r['status'])
            self.assertEqual('not_available', r['status'])
            if self.check_status_code:
                self.assertEqual('invalid_registration_plate', r['status_code'])

        # Check parking info
        log.debug(u'Получаю цену')
        service_descr = self.mk_service_descr(parking_id=parking_id,
                user_ticket=user_ticket, registration_plate=registration_plate)
        (avail_places, price) = self.get_avail_price(service_descr, user_id)

        # Create reservation
        log.debug(u'Создаю транзакцию')
        trans = self.random_id()
        r = self.iface.create_reservation(service_descr=service_descr,
                transaction_id=trans, price=price, user_id=user_id)
        self.assertEqual('success', r['status'])
        log.debug(u'Статус: %s' % r['status'])

        if self.check_avail:
            # Check available places
            (avail_places, _) = self.get_avail_price(service_descr, user_id)
            self.assertEqual(avail_places0, avail_places + 1)

        # Pay
        self.pay_trans(trans)

        # Do it twice
        log.debug(u'Пытаюсь оплатить повторно')
        self.pay_trans(trans)

        if self.check_avail:
            log.debug(u'Получаю цену для оплаченного тикета')
            r = self.iface.get_service_info(self.mk_service_descr(
                    parking_id=parking_id, user_ticket=user_ticket,
                    registration_plate=registration_plate), user_id=user_id)
            log.debug(u'Статус: %s' % r['status'])
            self.assertEqual('success', r['status'])
            log.debug(u'Тикет покидает парковку')
            r = self.iface.leave_parking(parking_id=parking_id,
                    user_ticket=user_ticket)
            log.debug(u'Статус: %s' % r['status'])
            self.assertEqual('success', r['status'])
            # Get service info by wrong params: paid user_ticket
            log.debug(u'Получаю цену для отработанного тикета')
            r = self.iface.get_service_info(self.mk_service_descr(
                    parking_id=parking_id, user_ticket=user_ticket,
                    registration_plate=registration_plate), user_id=user_id)
            self.assertEqual('not_available', r['status'])
            if self.target_version > 0:
                if self.check_status_code:
                    self.assertEqual('user_ticket_out_of_parking', r['status_code'])

        if self.check_avail:
            # Check available places
            service_descr = self.mk_service_descr(parking_id=parking_id,
                    duration=60, registration_plate=registration_plate)
            (avail_places, _) = self.get_avail_price(service_descr, user_id)
            self.assertEqual(avail_places0, avail_places)

        # Cancel reservation
        self.cancel_trans(trans)

def configure_logging():
    logging.basicConfig(
            format='%(asctime)s %(thread)d %(levelname)s %(name)s %(message)s')
    root_logger = logging.getLogger('')
    root_logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler('test.log')
    formatter = logging.Formatter('%(asctime)s %(thread)d %(levelname)s %(name)s %(message)s')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    root_logger.addHandler(fh)

def randomize():
    random.seed(int(time.time() * 1000))
    [random.random() for i in (1, 2, 3)]

if __name__ == '__main__':
    configure_logging()
    randomize()
    parser = optparse.OptionParser()
    parser.add_option('-t', '--target-version', dest='target_version',
            type='int', default=2,
            help='testing stand API version to test: 0, 1 or 2, '
            '[default:%default]')
    parser.add_option('-k', '--user-ticket', dest='user_ticket',
            help='provide user_ticket to run the postpay test against, '
            'use "random" for 13333 parking_id, [default:%default]')
    parser.add_option('-u', '--stand-uri', dest='stand_uri',
            help='URI of the testing stand, [default:%default]')
    parser.add_option('-p', '--check-plate', dest='check_plate',
            action='store_true', default=False,
            help='additionally check payment status by plate '
            '[default:%default]')
    parser.add_option('-a', '--check-avail', dest='check_avail',
            action='store_true', default=False,
            help='additionally check available space changes '
            '[default:%default]')
    parser.add_option('-e', '--no-check-status-code', dest='no_check_status_code',
            action='store_true', default=False,
            help='do not check for possible extended status codes '
            '[default:%default]')
    parser.add_option('-f', '--fake-stand', dest='fake_stand',
            action='store_true', default=False,
            help='load default settings for the fake testing stand '
            '[default:%default]')
    options, arguments = parser.parse_args()
    sys.argv = [sys.argv[0]]
    TestParkingHTTP.target_version = options.target_version
    TestParkingHTTP.user_ticket = options.user_ticket
    TestParkingHTTP.stand_uri = options.stand_uri
    TestParkingHTTP.check_plate = options.check_plate
    TestParkingHTTP.check_avail = options.check_avail
    TestParkingHTTP.check_status_code = not options.no_check_status_code
    TestParkingHTTP.fake_stand = options.fake_stand
    if options.fake_stand:
        TestParkingHTTP.stand_uri = 'http://localhost:8111/'
        #TestParkingHTTP.stand_uri = 'http://localhost:8112/parking/'
    TestParkingHTTP.print_settings()
    unittest.main()

