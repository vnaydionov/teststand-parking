#include "helpers.h"
#include "domain/Order.h"
#include "domain/Product.h"
#include "domain/Account.h"
#include "domain/Payment.h"
#include "domain/AccountReceipt.h"
#include "domain/AccountConsume.h"
#include "domain/AccountTransfer.h"

using namespace std;
using namespace Yb;
using namespace Domain;

ElementTree::ElementPtr mk_resp(const string &status,
        const string &status_code = "")
{
    ElementTree::ElementPtr res(ElementTree::new_json_dict());
    res->add_json_string("status", status);
    if (!status_code.empty())
        res->add_json_string("status_code", status_code);
    char buf[40];
    MilliSec t = get_cur_time_millisec();
    sprintf(buf, "%u.%03u", (unsigned)(t/1000), (unsigned)(t%1000));
    res->add_json("ts", buf);
    return res;
}

const Decimal round_hours(const Decimal &hours, bool first_hour) {
    LongInt minutes = (hours * 60).ipart();
    YB_ASSERT(minutes >= 0 && minutes < 1000000000);
    if (!minutes && first_hour)
        minutes = 1;
    minutes = ((minutes + 14) / 15) * 15;
    return Decimal(minutes) / 60;
}

const Decimal get_hours(const StringDict &service_descr) {
    Decimal duration = Decimal(service_descr.get("duration", "0"));
    if (duration <= Decimal(0))
        throw ApiResult(mk_resp("not_available", "invalid_duration"));
    return duration / 60;
}

Order get_order_by_ticket(Session &session, Product &parking,
        const string &user_ticket, bool lock) {
    Order order(EMPTY_DATAOBJ);
    try {
        QueryObj<Order> q = query<Order>(session).filter_by(
            (Order::c.product_id == parking.id) &&
            (Order::c.ticket_number == user_ticket));
        if (lock)
            q = q.for_update();
        order = q.one();
    }
    catch (const NoDataFound &) {
        throw ApiResult(mk_resp("not_available",
                    "user_ticket_not_found"));
    }
    if (order.finish_ts != Value())
        throw ApiResult(mk_resp("not_available",
                    "user_ticket_out_of_parking"));
    return order;
}

Order get_hours_and_price(Session &session,
        const StringDict &service_descr, Product &parking, bool lock,
        Decimal &hours, Decimal &price)
{
    Decimal price_per_hour;
    bool first_hour = true;
    auto_ptr<Order> result_order;
    Order order(EMPTY_DATAOBJ);
    if (service_descr.has("user_ticket")) {
        order = get_order_by_ticket(
                session, parking, service_descr["user_ticket"], lock);
        if (*order.product != parking)
            throw ApiResult(mk_resp("not_available", "user_ticket_not_found"));
        hours = Decimal(0);
        DateTime now_ts = now();
        if (now_ts > order.paid_until_ts)
            hours = Decimal(datetime_diff(order.paid_until_ts, now_ts)) / 3600;
        price_per_hour = order.price;
        first_hour = order.paid_until_ts == order.start_ts;
    }
    else {
        hours = get_hours(service_descr);
        price_per_hour = parking.price;
    }
    hours = round_hours(hours, first_hour);
    price = hours * price_per_hour;
    return order;
}

const Decimal get_account_balance(Session &session, const string &user_eid) {
    try {
        Account acc = query<Account>(session).filter_by(
                Account::c.user_eid == user_eid).one();
        return acc.balance;
    }
    catch (const NoDataFound &) {
        return Decimal(0);
    }
}

Account get_account(Session &session, const string &user_eid) {
    Account account(EMPTY_DATAOBJ);
    try {
        account = query<Account>(session).for_update()
                .filter_by(Account::c.user_eid == user_eid).one();
    }
    catch (const NoDataFound &) {
        account = Account(session);
        account.user_eid = user_eid;
        session.flush();
    }
    return account;
}

void create_account_receipt(Session &session, const string &user_eid,
        Order &order, const Decimal &amount) {
    Account account = get_account(session, user_eid);
    YB_ASSERT(amount <= order.paid_amount);
    AccountReceipt receipt(session);
    receipt.account = Account::Holder(account);
    receipt.src_order = Order::Holder(order);
    receipt.amount = amount;
    account.balance = account.balance + amount;
    order.paid_amount = order.paid_amount - amount;
    order.paid_until_ts = now();
    session.flush();
}

void create_account_consume(Session &session, const string &user_eid,
        Payment &payment, const Decimal &amount, bool reserve) {
    Account account = get_account(session, user_eid);
    YB_ASSERT(amount <= account.balance - account.reserved);
    AccountConsume consume(session);
    consume.account = Account::Holder(account);
    consume.dst_payment = Payment::Holder(payment);
    consume.amount = amount;
    consume.is_reserved = int(reserve);
    if (reserve)
        account.reserved = account.reserved + amount;
    else
        account.balance = account.balance - amount;
    payment.amount = payment.amount + amount;
    session.flush();
}

void fix_consume(Session &session, Payment &payment, bool approve) {
    YB_ASSERT(payment.consumes.size() == 1);
    AccountConsume consume = *payment.consumes.begin();
    Account account = *consume.account;
    lock_and_refresh(session, account);
    lock_and_refresh(session, consume);
    YB_ASSERT(account.reserved.value() >= consume.amount);
    account.reserved = account.reserved - consume.amount;
    if (approve) {
        YB_ASSERT(account.balance.value() >= consume.amount);
        account.balance = account.balance - consume.amount;
    }
    else
        consume.amount = Decimal(0);
    consume.is_reserved = 0;
    session.flush();
}

ElementTree::ElementPtr get_service_info(Session &session, ILogger &logger,
        const StringDict &params) {
    string service_descr_str = params["service_descr"];
    string user_eid = params.get("user_id", "");
    if (user_eid.empty())
        throw ApiResult(mk_resp("not_available", "invalid_user_id"));
    StringDict service_descr = json2dict(service_descr_str);
    logger.debug("service_descr: " + dict2str(service_descr));
    Product parking;
    try {
        string parking_name = service_descr["parking_id"];
        parking = query<Product>(session)
            .filter_by(Product::c.name == parking_name).one();
    }
    catch (const NoDataFound &) {
        throw ApiResult(mk_resp("not_available", "invalid_parking_id"));
    }
    Decimal price, hours;
    Order order(get_hours_and_price(
            session, service_descr, parking, false, hours, price));
    ElementTree::ElementPtr resp = mk_resp("success");
    resp->add_json("price", money2str(price));
    ElementTree::ElementPtr info = resp->add_json_dict("info");
    info->add_json("available_places", parking.places_avail.value());
    if (!order.is_empty()) {
        info->add_json("start_ts",
                timestamp2str(datetime2timestamp(order.start_ts)));
        if (service_descr.has("user_ticket"))
            info->add_json("paid_duration",
                    Decimal(datetime_diff(order.start_ts,
                            order.paid_until_ts) / 60).round());
    }
    else {
        info->add_json("start_ts",
                timestamp2str(datetime2timestamp(now())));
    }
    info->add_json("duration", (hours * 60).round());
    info->add_json("balance", money2str(
            get_account_balance(session, user_eid)));
    throw ApiResult(resp);
}

ElementTree::ElementPtr create_reservation(Session &session, ILogger &logger,
        const StringDict &params) {
    string user_eid = params.get("user_id", "");
    if (user_eid.empty())
        throw ApiResult(mk_resp("not_available", "invalid_user_id"));
    StringDict service_descr = json2dict(params["service_descr"]);
    logger.debug("service_descr: " + dict2str(service_descr));
    Product parking(EMPTY_DATAOBJ);
    try {
        string parking_name = service_descr["parking_id"];
        parking = query<Product>(session).for_update()
            .filter_by(Product::c.name == parking_name).one();
    }
    catch (const NoDataFound &) {
        throw ApiResult(mk_resp("not_available", "invalid_parking_id"));
    }
    string plate_number = service_descr.get("registration_plate", "");
    if (plate_number.empty())
        throw ApiResult(mk_resp("not_available", "invalid_registration_plate"));
    Decimal price0 = Decimal(params["price"]);
    Decimal pay_from_balance = Decimal(params["pay_from_balance"]);
    if (pay_from_balance < Decimal(0) || pay_from_balance > price0)
        throw ApiResult(mk_resp("wrong_price"));
    string transaction_eid = params.get("transaction_id", "");
    if (transaction_eid.size() < 4 || transaction_eid.size() > 64)
        throw ApiResult(mk_resp("bad_transaction"));
    try {
        Payment payment = query<Payment>(session).for_update()
                .filter_by(Payment::c.trans_number == transaction_eid).one();
        if (payment.amount == price0 && *payment.order->product == parking)
            throw ApiResult(mk_resp("success"));
        throw ApiResult(mk_resp("wrong_price"));
    }
    catch (const NoDataFound &) {}
    Decimal price, hours;
    Order order(get_hours_and_price(
            session, service_descr, parking, true, hours, price));
    if (price != price0)
        throw ApiResult(mk_resp("wrong_price"));
    if (parking.places_avail == 0)
        throw ApiResult(mk_resp("not_available"));
    if (order.is_empty()) {
        order = Order(session);
        order.product = Product::Holder(parking);
        order.user_eid = user_eid;
        order.plate_number = plate_number;
        order.start_ts = now();
        order.paid_until_ts = order.start_ts;
        order.price = parking.price;
    }
    Payment payment;
    payment.trans_number = transaction_eid;
    payment.hours = hours;
    payment.order = Order::Holder(order);
    payment.amount = price - pay_from_balance;
    payment.ts = order.start_ts;
    payment.save(session);
    if (pay_from_balance > 0) {
        create_account_consume(session, user_eid, payment,
                pay_from_balance, true);
    }
    ElementTree::ElementPtr resp = mk_resp("success");
    resp->add_json("price", money2str(price));
    ElementTree::ElementPtr info = resp->add_json_dict("info");
    info->add_json("start_ts",
            timestamp2str(datetime2timestamp(order.start_ts)));
    info->add_json("duration", (hours * 60).round());
    if (service_descr.has("user_ticket"))
        info->add_json("paid_duration", Decimal(0));
    return resp;
}

ElementTree::ElementPtr pay_reservation(Session &session, ILogger &logger,
        const StringDict &params) {
    string transaction_eid = params.get("transaction_id", "");
    if (transaction_eid.size() < 4 || transaction_eid.size() > 64)
        throw ApiResult(mk_resp("bad_transaction"));
    Payment payment(EMPTY_DATAOBJ);
    try {
        payment = query<Payment>(session).for_update()
                .filter_by(Payment::c.trans_number == transaction_eid).one();
    }
    catch (const NoDataFound &) {
        throw ApiResult(mk_resp("bad_transaction"));
    }
    if (payment.payment_ts != Value())
        throw ApiResult(mk_resp("success"));
    if (payment.cancel_ts != Value())
        throw ApiResult(mk_resp("bad_transaction"));
    Order order = lock_and_refresh(session, *payment.order);
    DateTime now_ts = now();
    payment.payment_ts = now_ts;
    order.paid_amount = order.paid_amount + payment.amount;
    order.paid_until_ts = dt_add_seconds(order.paid_until_ts,
            (payment.hours * 3600).ipart());
    if (order.ticket_number == Value() && now_ts < order.paid_until_ts) {
        Product product = query<Product>(session).for_update()
                .filter_by(Product::c.id == order.product->id).one();
        product.places_avail = product.places_avail - 1;
    }
    if (payment.consumes.size())
        fix_consume(session, payment, true);
    return mk_resp("success");
}

ElementTree::ElementPtr cancel_reservation(Session &session, ILogger &logger,
        const StringDict &params) {
    string transaction_eid = params.get("transaction_id", "");
    if (transaction_eid.size() < 4 || transaction_eid.size() > 64)
        throw ApiResult(mk_resp("bad_transaction"));
    Payment payment(EMPTY_DATAOBJ);
    try {
        payment = query<Payment>(session).for_update()
                .filter_by(Payment::c.trans_number == transaction_eid).one();
    }
    catch (const NoDataFound &) {
        throw ApiResult(mk_resp("bad_transaction"));
    }
    if (payment.cancel_ts != Value())
        throw ApiResult(mk_resp("success"));
    Order order = query<Order>(session).for_update()
            .filter_by(Order::c.id == payment.order->id).one();
    DateTime now_ts = now();
    payment.cancel_ts = now_ts;
    if (payment.payment_ts != Value()) {
        order.paid_amount = order.paid_amount - payment.amount;
        order.paid_until_ts = dt_add_seconds(order.paid_until_ts,
                -(payment.hours * 3600).ipart());
        if (order.ticket_number == Value() && now_ts >= order.paid_until_ts) {
            order.finish_ts = now_ts;
            Product product = query<Product>(session).for_update()
                    .filter_by(Product::c.id == order.product->id).one();
            product.places_avail = product.places_avail + 1;
        }
    }
    else
        order.finish_ts = now_ts;
    if (payment.consumes.size())
        fix_consume(session, payment, false);
    return mk_resp("success");
}

ElementTree::ElementPtr stop_service(Session &session, ILogger &logger,
        const StringDict &params) {
    string transaction_eid = params.get("transaction_id", "");
    if (transaction_eid.size() < 4 || transaction_eid.size() > 64)
        throw ApiResult(mk_resp("bad_transaction"));
    Payment payment(EMPTY_DATAOBJ);
    try {
        payment = query<Payment>(session).for_update()
                .filter_by(Payment::c.trans_number == transaction_eid).one();
    }
    catch (const NoDataFound &) {
        throw ApiResult(mk_resp("bad_transaction"));
    }
    if (payment.payment_ts == Value() || payment.cancel_ts != Value())
        throw ApiResult(mk_resp("bad_transaction"));
    Order order = query<Order>(session).for_update()
            .filter_by(Order::c.id == payment.order->id).one();
    if (order.ticket_number != Value())
        throw ApiResult(mk_resp("bad_transaction"));
    int existing_cnt = order.receipts.size();
    ElementTree::ElementPtr resp = mk_resp("success");
    if (existing_cnt) {
        YB_ASSERT(existing_cnt == 1);
        resp->add_json("delta_amount", money2str(
                    order.receipts.begin()->amount));
        throw ApiResult(resp);
    }
    DateTime now_ts = now();
    if (now_ts >= order.paid_until_ts) {
        resp->add_json("delta_amount", money2str(Decimal(0)));
        throw ApiResult(resp);
    }
    int total_secs_left = datetime_diff(now_ts, order.paid_until_ts) - 1;
    int duration_left = (total_secs_left / (15 * 60)) * 15; // rounded minutes
    Decimal price_per_minute = order.paid_amount / Decimal(datetime_diff(
                order.start_ts, order.paid_until_ts) / 60);
    Decimal delta_amount = (duration_left * price_per_minute).round(2);
    logger.debug("total_seconds_left=" + to_string(total_secs_left) +
            " duration_left=" + to_string(duration_left) +
            " price=" + money2str(price_per_minute) +
            " delta=" + money2str(delta_amount));
    create_account_receipt(session, order.user_eid, order, delta_amount);
    resp->add_json("delta_amount", money2str(delta_amount));
    return resp;
}

ElementTree::ElementPtr get_user_account(Session &session, ILogger &logger,
        const StringDict &params) {
    string user_eid = params.get("user_id", "");
    if (user_eid.empty())
        throw ApiResult(mk_resp("not_available", "invalid_user_id"));
    ElementTree::ElementPtr res = mk_resp("success");
    res->add_json("balance", money2str(get_account_balance(session, user_eid)));
    return res;
}

ElementTree::ElementPtr account_transfer(Session &session, ILogger &logger,
        const StringDict &params) {
    string src_user_eid = params.get("src_user_id", ""),
            dst_user_eid = params.get("dst_user_id", ""),
            transaction_eid = params.get("transaction_id", "");
    if (src_user_eid.empty() || dst_user_eid.empty())
        throw ApiResult(mk_resp("bad_transaction", "invalid_user_id"));
    if (transaction_eid.empty())
        throw ApiResult(mk_resp("bad_transaction", "transaction_id"));
    Account src_account = get_account(session, src_user_eid),
            dst_account = get_account(session, dst_user_eid);
    if (src_account == dst_account)
        throw ApiResult(mk_resp("bad_transaction", "same_src_and_dst"));
    DomainResultSet<AccountTransfer> rs = query<AccountTransfer>(session)
        .for_update()
        .filter_by(AccountTransfer::c.trans_number == transaction_eid).all();
    if (rs.begin() != rs.end()) {
        AccountTransfer existing_transfer = *rs.begin();
        if (*existing_transfer.src_account != src_account
                || *existing_transfer.dst_account != dst_account)
            throw ApiResult(mk_resp("bad_transaction", "another_trans_exists"));
        throw ApiResult(mk_resp("success", "already_done"));
    }
    if (src_account.balance <= Decimal(0))
        throw ApiResult(mk_resp("success", "nothing_to_transfer"));
    if (src_account.reserved != Decimal(0))
        throw ApiResult(mk_resp("not_available", "reserved_funds_present"));
    Decimal amount = src_account.balance;
    AccountTransfer trans(session);
    trans.ts = now();
    trans.trans_number = transaction_eid;
    trans.src_account = Account::Holder(src_account);
    trans.dst_account = Account::Holder(dst_account);
    trans.amount = amount;
    src_account.balance = src_account.balance - amount;
    dst_account.balance = dst_account.balance + amount;
    return mk_resp("success");
}

ElementTree::ElementPtr issue_ticket(Session &session, ILogger &logger,
        const StringDict &params) {
    string parking_name = params["parking_id"];
    YB_ASSERT(!parking_name.empty());
    Product parking = query<Product>(session).for_update()
        .filter_by(Product::c.name == parking_name).one();
    YB_ASSERT(parking.places_avail > 0);
    string ticket_number;
    while (1) {
        double rnd = rand() / (RAND_MAX + 1.0);
        ticket_number = to_string((int)(rnd * 1000000000 + 1000000000));
        if (!query<Order>(session).filter_by(
                    Order::c.ticket_number == ticket_number).count())
            break;
    }
    Order order(session);
    order.product = Product::Holder(parking);
    order.ticket_number = ticket_number;
    order.start_ts = now();
    order.paid_until_ts = order.start_ts;
    order.price = parking.price;
    parking.places_avail = parking.places_avail - 1;
    ElementTree::ElementPtr res = mk_resp("success");
    res->add_json_string("user_ticket", ticket_number);
    res->add_json("available_places", parking.places_avail.value());
    return res;
}

ElementTree::ElementPtr leave_parking(Session &session, ILogger &logger,
        const StringDict &params) {
    DateTime now_ts = now();
    string parking_name = params["parking_id"];
    string user_ticket = params["user_ticket"];
    Product parking = query<Product>(session)
        .filter_by(Product::c.name == parking_name).one();
    Order order = query<Order>(session).for_update()
        .filter_by(
            (Order::c.ticket_number == user_ticket) &&
            (Order::c.product_id == parking.id) &&
            (Order::c.finish_ts == Value())).one();
    if (order.start_ts == order.paid_until_ts ||
            now_ts >= dt_add_seconds(order.paid_until_ts, 15*60))
        throw ApiResult(mk_resp("not_enough_paid"));
    order.finish_ts = now_ts;
    parking = query<Product>(session).for_update()
        .filter_by(Product::c.id == parking.id).one();
    parking.places_avail = parking.places_avail + 1;
    return mk_resp("success");
}

ElementTree::ElementPtr check_plate_number(Session &session, ILogger &logger,
        const StringDict &params) {
    string plate_number = params["registration_plate"];
    YB_ASSERT(!plate_number.empty());
    int active_orders_count = query<Order>(session).filter_by(
            (Order::c.plate_number == plate_number) &&
            (Order::c.paid_until_ts > now()) &&
            (Order::c.finish_ts == Value())).count();
    ElementTree::ElementPtr res = mk_resp("success");
    res->add_json_string("paid", active_orders_count >= 1? "true": "false");
    throw ApiResult(res);
}

typedef ElementTree::ElementPtr (*HttpHandler)(
        Session &session, ILogger &logger,
        const StringDict &params);

class ParkingHttpWrapper
{
    string name_, default_status_;
    HttpHandler f_;
    string dump_result(ILogger &logger, ElementTree::ElementPtr res)
    {
        string res_str = etree2json(res);
        logger.info("result: " + res_str);
        return res_str;
    }
public:
    ParkingHttpWrapper(): f_(NULL) {}
    ParkingHttpWrapper(const string &name, HttpHandler f,
            const string &default_status = "not_available")
        : name_(name), default_status_(default_status), f_(f)
    {}
    const string &name() const { return name_; }
    string operator() (const StringDict &params)
    {
        ILogger::Ptr logger(theApp::instance().new_logger(name_));
        TimerGuard t(*logger);
        try {
            logger->info("started, params: " + dict2str(params));
            int version = params.get_as<int>("version");
            YB_ASSERT(version >= 2);
            auto_ptr<Session> session(
                    theApp::instance().new_session());
            ElementTree::ElementPtr res = f_(*session, *logger, params);
            session->commit();
            t.set_ok();
            return dump_result(*logger, res);
        }
        catch (const ApiResult &ex) {
            t.set_ok();
            return dump_result(*logger, ex.result());
        }
        catch (const exception &ex) {
            logger->error(string("exception: ") + ex.what());
            return dump_result(*logger, mk_resp(default_status_));
        }
    }
};

#define WRAP(func) ParkingHttpWrapper(#func, func)

int main(int argc, char *argv[])
{
    string log_name = "parkingxx.log";
    string db_name = "parkingxx_db";
    string error_content_type = "text/json";
    string error_body = "{\"status\": \"internal_error\"}";
    string prefix = "/parking/";
    int port = 8112;
    ParkingHttpWrapper handlers[] = {
        WRAP(get_service_info),
        WRAP(create_reservation),
        WRAP(pay_reservation),
        WRAP(cancel_reservation),
        WRAP(stop_service),
        WRAP(get_user_account),
        WRAP(account_transfer),
        WRAP(issue_ticket),
        WRAP(leave_parking),
        WRAP(check_plate_number),
    };
    int n_handlers = sizeof(handlers)/sizeof(handlers[0]);
    return run_server_app(log_name, db_name, port,
            handlers, n_handlers, error_content_type, error_body, prefix);
}

// vim:ts=4:sts=4:sw=4:et:
