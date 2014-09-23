#ifndef _PARKINGXX__MODEL_H_
#define _PARKINGXX__MODEL_H_

#include "orm/domain_object.h"
#include "orm/domain_factory.h"
#include "orm/schema_decl.h"

class Order;

class Product: public Yb::DomainObject {

YB_DECLARE(Product, "T_PRODUCT", "S_PRODUCT", "product",
    YB_COL_PK(id, "ID")
    YB_COL_STR(name, "NAME", 100)
    YB_COL_STR(display_name, "DISPLAY_NAME", 200)
    YB_COL_DATA(places_avail, "PLACES_AVAIL", INTEGER)
    YB_COL_DATA(price, "PRICE", DECIMAL)
    YB_REL_ONE(Product, product, Order, orders,
               Yb::Relation::Restrict, "PRODUCT_ID", 1, "")
    YB_COL_END)

};

class Payment;
class AccountReceipt;

class Order: public Yb::DomainObject {

YB_DECLARE(Order, "T_ORDER", "S_ORDER", "order",
    YB_COL_PK(id, "ID")
    YB_COL_FK(product_id, "PRODUCT_ID", "T_PRODUCT", "ID")
    YB_COL_STR(user_eid, "USER_EID", 100)
    YB_COL_STR(ticket_number, "TICKET_NUMBER", 100)
    YB_COL_STR(plate_number, "PLATE_NUMBER", 20)
    YB_COL_DATA(start_ts, "START_TS", DATETIME)
    YB_COL_DATA(paid_until_ts, "PAID_UNTIL_TS", DATETIME)
    YB_COL_DATA(finish_ts, "FINISH_TS", DATETIME)
    YB_COL(paid_amount, "PAID_AMOUNT", DECIMAL, 0, 0, 0, "", "", "", "")
    YB_COL_DATA(price, "PRICE", DECIMAL)
    YB_REL_MANY(Product, product, Order, orders,
                Yb::Relation::Restrict, "PRODUCT_ID", 1, "")
    YB_REL_ONE(Order, order, Payment, payments,
               Yb::Relation::Restrict, "ORDER_ID", 1, "")
    YB_REL_ONE(Order, src_order, AccountReceipt, receipts,
               Yb::Relation::Restrict, "SRC_ORDER_ID", 1, "")
    YB_COL_END)

};

class AccountConsume;

class Payment: public Yb::DomainObject {

YB_DECLARE(Payment, "T_PAYMENT", "S_PAYMENT", "payment",
    YB_COL_PK(id, "ID")
    YB_COL_STR(trans_number, "TRANS_NUMBER", 100)
    YB_COL_FK(order_id, "ORDER_ID", "T_ORDER", "ID")
    YB_COL_DATA(ts, "TS", DATETIME)
    YB_COL_DATA(hours, "HOURS", DECIMAL)
    YB_COL_DATA(amount, "AMOUNT", DECIMAL)
    YB_COL_DATA(payment_ts, "PAYMENT_TS", DATETIME)
    YB_COL_DATA(cancel_ts, "CANCEL_TS", DATETIME)
    YB_REL_MANY(Order, order, Payment, payments,
                Yb::Relation::Restrict, "ORDER_ID", 1, "")
    YB_REL_ONE(Payment, dst_payment, AccountConsume, consumes,
               Yb::Relation::Restrict, "", 1, "")
    YB_COL_END)

};

class Account: public Yb::DomainObject {

YB_DECLARE(Account, "T_ACCOUNT", "S_ACCOUNT", "account",
    YB_COL_PK(id, "ID")
    YB_COL_STR(user_eid, "USER_EID", 100)
    YB_COL(balance, "BALANCE", DECIMAL, 0, 0, 0, "", "", "", "")
    YB_COL(reserved, "RESERVED", DECIMAL, 0, 0, 0, "", "", "", "")
    YB_REL_ONE(Account, account, AccountReceipt, receipts,
               Yb::Relation::Restrict, "ACCOUNT_ID", 1, "")
    YB_REL_ONE(Account, account, AccountConsume, consumes,
               Yb::Relation::Restrict, "ACCOUNT_ID", 1, "")
    YB_COL_END)

};

class AccountReceipt: public Yb::DomainObject {

YB_DECLARE(AccountReceipt, "T_ACCOUNT_RECEIPT", "S_ACCOUNT_RECEIPT", "account_receipt",
    YB_COL_PK(id, "ID")
    YB_COL_DATA(ts, "TS", DATETIME)
    YB_COL_FK(account_id, "ACCOUNT_ID", "T_ACCOUNT", "ID")
    YB_COL_FK(src_order_id, "SRC_ORDER_ID", "T_ORDER", "ID")
    YB_COL_DATA(amount, "AMOUNT", DECIMAL)
    YB_REL_MANY(Account, account, AccountReceipt, receipts,
                Yb::Relation::Restrict, "ACCOUNT_ID", 1, "")
    YB_REL_MANY(Order, src_order, AccountReceipt, receipts,
                Yb::Relation::Restrict, "SRC_ORDER_ID", 1, "")
    YB_COL_END)

};

class AccountConsume: public Yb::DomainObject {

YB_DECLARE(AccountConsume, "T_ACCOUNT_CONSUME", "S_ACCOUNT_CONSUME", "account_consume",
    YB_COL_PK(id, "ID")
    YB_COL_DATA(ts, "TS", DATETIME)
    YB_COL_FK(account_id, "ACCOUNT_ID", "T_ACCOUNT", "ID")
    YB_COL_FK(dst_payment_id, "DST_PAYMENT_ID", "T_PAYMENT", "ID")
    YB_COL_DATA(amount, "AMOUNT", DECIMAL)
    YB_COL_DATA(is_reserved, "IS_RESERVED", INTEGER)
    YB_REL_MANY(Account, account, AccountConsume, consumes,
                Yb::Relation::Restrict, "", 1, "")
    YB_REL_MANY(Payment, dst_payment, AccountConsume, consumes,
                Yb::Relation::Restrict, "", 1, "")
    YB_COL_END)

};

class AccountTransfer: public Yb::DomainObject {

YB_DECLARE(AccountTransfer, "T_ACCOUNT_TRANSFER", "S_ACCOUNT_TRANSFER", "account_transfer",
    YB_COL_PK(id, "ID")
    YB_COL_DATA(ts, "TS", DATETIME)
    YB_COL_STR(trans_number, "TRANS_NUMBER", 100)
    YB_COL_FK(src_account_id, "SRC_ACCOUNT_ID", "T_ACCOUNT", "ID")
    YB_COL_FK(dst_account_id, "DST_ACCOUNT_ID", "T_ACCOUNT", "ID")
    YB_COL_DATA(amount, "AMOUNT", DECIMAL)
    YB_REL_MANY(Account, src_account, AccountTransfer, ,
                Yb::Relation::Restrict, "SRC_ACCOUNT_ID", 1, "")
    YB_REL_MANY(Account, dst_account, AccountTransfer, ,
                Yb::Relation::Restrict, "DST_ACCOUNT_ID", 1, "")
    YB_COL_END)

};

#endif // _PARKINGXX__MODEL_H_
// vim:ts=4:sts=4:sw=4:et:
