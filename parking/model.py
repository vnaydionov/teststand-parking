# -*- coding: utf-8 -*-

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, ForeignKey, \
        Integer, BigInteger, String, DateTime, Numeric
from sqlalchemy.orm import relationship, backref

Base = declarative_base()

class Product(Base):
    __tablename__ = 'T_PRODUCT'

    id = Column(BigInteger, primary_key=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)
    places_avail = Column(Integer, nullable=False)
    price = Column(Numeric, nullable=False)

class Order(Base):
    __tablename__ = 'T_ORDER'

    id = Column(BigInteger, primary_key=True)
    product_id = Column(BigInteger, ForeignKey('T_PRODUCT.id'), nullable=False)
    user_eid = Column(String(100))
    ticket_number = Column(String(100))
    plate_number = Column(String(20))
    start_ts = Column(DateTime, nullable=False)
    paid_until_ts = Column(DateTime, nullable=False)
    finish_ts = Column(DateTime)
    paid_amount = Column(Numeric)
    price = Column(Numeric)

    product = relationship(Product, backref=backref('orders'))

class Payment(Base):
    __tablename__ = 'T_PAYMENT'

    id = Column(BigInteger, primary_key=True)
    trans_number = Column(String(100), nullable=False)
    order_id = Column(BigInteger, ForeignKey('T_ORDER.id'), nullable=False)
    ts = Column(DateTime, nullable=False)
    hours = Column(Numeric)
    amount = Column(Numeric)
    payment_ts = Column(DateTime)
    cancel_ts = Column(DateTime)

    order = relationship(Order, backref=backref('payments'))

class Account(Base):
    __tablename__ = 'T_ACCOUNT'

    id = Column(BigInteger, primary_key=True)
    user_eid = Column(String(100), nullable=False)
    balance = Column(Numeric, nullable=False)
    reserved = Column(Numeric, nullable=False)

class AccountReceipt(Base):
    __tablename__ = 'T_ACCOUNT_RECEIPT'

    id = Column(BigInteger, primary_key=True)
    ts = Column(DateTime, nullable=False)
    account_id = Column(BigInteger, ForeignKey('T_ACCOUNT.id'), nullable=False)
    src_order_id = Column(BigInteger, ForeignKey('T_ORDER.id'),
            nullable=False)
    amount = Column(Numeric, nullable=False)

    account = relationship(Account, backref=backref('receipts'))
    src_order = relationship(Order, backref=backref('receipts'))

class AccountConsume(Base):
    __tablename__ = 'T_ACCOUNT_CONSUME'

    id = Column(BigInteger, primary_key=True)
    ts = Column(DateTime, nullable=False)
    account_id = Column(BigInteger, ForeignKey('T_ACCOUNT.id'), nullable=False)
    dst_payment_id = Column(BigInteger, ForeignKey('T_PAYMENT.id'),
            nullable=False)
    amount = Column(Numeric, nullable=False)
    is_reserved = Column(Integer, nullable=False)

    account = relationship(Account, backref=backref('consumes'))
    dst_payment = relationship(Payment, backref=backref('consumes'))

class AccountTransfer(Base):
    __tablename__ = 'T_ACCOUNT_TRANSFER'

    id = Column(BigInteger, primary_key=True)
    ts = Column(DateTime, nullable=False)
    trans_number = Column(String(100), nullable=False)
    src_account_id = Column(BigInteger, ForeignKey('T_ACCOUNT.id'), nullable=False)
    dst_account_id = Column(BigInteger, ForeignKey('T_ACCOUNT.id'), nullable=False)
    amount = Column(Numeric, nullable=False)

    src_account = relationship(Account,
            primaryjoin="Account.id==AccountTransfer.src_account_id")
    dst_account = relationship(Account,
            primaryjoin="Account.id==AccountTransfer.dst_account_id")

