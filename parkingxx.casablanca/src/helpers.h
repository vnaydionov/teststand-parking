#ifndef _PARKINGXX__HELPERS_H_
#define _PARKINGXX__HELPERS_H_

#include <cstdio>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <util/nlogger.h>
#include <orm/data_object.h>
#include <pplx/pplx.h>
#include <cpprest/http_client.h>
#include <cpprest/http_listener.h>
#include <cpprest/json.h>
#include "app_class.h"

const std::string money2str(const Yb::Decimal &x);
const std::string timestamp2str(double ts);
double datetime2timestamp(const Yb::DateTime &d);
double datetime_diff(const Yb::DateTime &a, const Yb::DateTime &b);
const std::string dict2str(const Yb::StringDict &params);
void randomize();

template <class HttpHandler>
inline int run_server_app(const std::string &log_name, const std::string &db_name,
        int port, HttpHandler *handlers_array, int n_handlers,
        const std::string &prefix = "")
{
    randomize();
    Yb::ILogger::Ptr log;
    try {
        theApp::instance().init(log_name, db_name);
        log.reset(theApp::instance().new_logger("main").release());
    }
    catch (const std::exception &ex) {
        std::cerr << "exception: " << ex.what() << "\n";
        return 1;
    }
    try {
        using namespace web::http;
        using namespace web::http::experimental::listener;
        std::string listen_at = "http://0.0.0.0:"
                + boost::lexical_cast<std::string>(port)
                + "/";
        log->error("listen at: " + listen_at);
        http_listener listener(listen_at);
        auto http_handler =
            [&](http_request request)
            {
                bool found = false;
                const auto &uri = request.relative_uri();
                for (int i = 0; i < n_handlers; ++i) {
                    if (uri.path() == prefix + handlers_array[i].name())
                    {
                        handlers_array[i](request);
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    web::http::http_response resp(
                            web::http::status_codes::NotFound);
                    request.reply(resp);
                }
            };
        listener.support(methods::GET, http_handler);
        listener.support(methods::POST, http_handler);
        listener.open().wait();
        log->error(std::string("open().wait() finished"));
        while (true) {
            sleep(100);
        }
    }
    catch (const std::exception &ex) {
        log->error(std::string("exception: ") + ex.what());
        return 1;
    }
    return 0;
}

class TimerGuard
{
    Yb::ILogger &logger_;
    Yb::MilliSec t0_;
    bool except_;
public:
    TimerGuard(Yb::ILogger &logger)
        : logger_(logger), t0_(Yb::get_cur_time_millisec()), except_(true)
    {}
    void set_ok() { except_ = false; }
    Yb::MilliSec time_spent() const
    {
        return Yb::get_cur_time_millisec() - t0_;
    }
    ~TimerGuard() {
        std::ostringstream out;
        out << "finished";
        if (except_)
            out << " with an exception";
        out << ", " << time_spent() << " ms";
        logger_.info(out.str());
    }
};

class ApiResult: public std::runtime_error
{
    std::shared_ptr<web::json::value> p_;
public:
    explicit ApiResult(std::unique_ptr<web::json::value> p)
        : runtime_error("api result"), p_(p.release())
    {}
    virtual ~ApiResult() throw () {}
    web::json::value &result() const { return *p_.get(); }
    web::json::value *release_result() {
        web::json::value *r = p_.get();
        p_.reset();
        return r;
    }
};

inline std::unique_ptr<web::json::value> mk_resp(const Yb::String &status,
        const Yb::String &status_code = _T(""))
{
    std::unique_ptr<web::json::value> res_holder(new web::json::value);
    web::json::value &res = *res_holder;
    res["status"] = web::json::value(status);
    if (!Yb::str_empty(status_code))
        res["status_code"] = web::json::value(status_code);
    char buf[40];
    Yb::MilliSec t = Yb::get_cur_time_millisec();
    std::sprintf(buf, "%u.%03u", (unsigned)(t/1000), (unsigned)(t%1000));
    res["ts"] = web::json::value(WIDEN(buf));
    return res_holder;
}

template <class http_msg>
inline std::string extract_body(http_msg &request, Yb::ILogger &log)
{
    log.debug("extract_body() got called");
    auto body_task = request.extract_string();
    if (body_task.wait() != pplx::completed)
        throw Yb::RunTimeError("pplx: body_task.wait() failed");
    std::string result = body_task.get();
    //log.debug("extract_body(): " + result);
    return result;
}

inline const std::string uri_decode(const std::string &s)
{
    std::string t = s;
    for (size_t i = 0; i < t.size(); ++i)
        if (t[i] == '+')
            t[i] = ' ';
    return web::http::uri::decode(t);
}

inline const Yb::StringDict get_params(web::http::http_request &request, Yb::ILogger &log)
{
    // parse query string
    const auto &uri = request.relative_uri();
    auto uri_params = web::http::uri::split_query(uri.query());
    // get request body
    auto body = extract_body(request, log);
    // check Content-Type
    std::map<std::string, std::string> body_params;
    if (request.headers().content_type()
            == "application/x-www-form-urlencoded")
        body_params = web::http::uri::split_query(body);
    // fill params
    Yb::StringDict params;
    for (const auto &p: uri_params)
        params[p.first] = uri_decode(p.second);
    for (const auto &p: body_params)
        params[p.first] = uri_decode(p.second);
    log.debug("get_params(): " + dict2str(params));
    return params;
}

inline const Yb::StringDict json2dict(const Yb::String &s)
{
    std::istringstream inp(s);
    web::json::value input_json;
    inp >> input_json;
    Yb::StringDict result;
    for (const auto &p : input_json.as_object()) {
        result[p.first] = p.second.as_string();
    }
    return result;
}

typedef std::unique_ptr<web::json::value> (*JsonHttpHandler)(
        Yb::Session &session, Yb::ILogger &logger,
        const Yb::StringDict &params);

class JsonHttpWrapper
{
    Yb::String name_, default_status_;
    JsonHttpHandler f_;

    std::string dump_result(Yb::ILogger &logger, web::json::value &res)
    {
        std::string res_str = res.serialize();
        logger.info("result: " + res_str);
        return res_str;
    }

public:
    JsonHttpWrapper(): f_(NULL) {}

    JsonHttpWrapper(const Yb::String &name, JsonHttpHandler f,
            const Yb::String &default_status = _T("not_available"))
        : name_(name), default_status_(default_status), f_(f)
    {}

    const Yb::String &name() const { return name_; }

    void operator() (web::http::http_request &request)
    {
        Yb::ILogger::Ptr logger(theApp::instance().new_logger(NARROW(name_)));
        TimerGuard t(*logger);
        try {
            const auto &uri = request.relative_uri();
            const auto &path = uri.path();
            const Yb::StringDict params = get_params(request, *logger);
            logger->info("started path: " + path
                         + ", params: " + dict2str(params));
            int version = params.get_as<int>("version");
            YB_ASSERT(version >= 2);
            // call xml wrapped
            std::unique_ptr<Yb::Session> session(
                    theApp::instance().new_session());
            std::unique_ptr<web::json::value> res = f_(*session, *logger, params);
            session->commit();
            // form the reply
            web::http::http_response resp(web::http::status_codes::OK);
            resp.set_body(dump_result(*logger, *res), "text/json");
            request.reply(resp);
        }
        catch (ApiResult &ex) {
            web::http::http_response resp(web::http::status_codes::OK);
            resp.set_body(dump_result(*logger, ex.result()), "text/json");
            request.reply(resp);
            t.set_ok();
        }
        catch (const std::exception &ex) {
            logger->error(std::string("exception: ") + ex.what());
            web::http::http_response resp(web::http::status_codes::InternalError);
            resp.set_body(dump_result(*logger, *mk_resp(default_status_)),
                          "text/json");
            request.reply(resp);
        }
        catch (...) {
            logger->error("unknown exception");
            web::http::http_response resp(web::http::status_codes::InternalError);
            resp.set_body(dump_result(*logger, *mk_resp(default_status_)),
                          "text/json");
            request.reply(resp);
        }
    }
};

#define WRAP(func) JsonHttpWrapper(_T(#func), func)

#endif // _PARKINGXX__HELPERS_H_
// vim:ts=4:sts=4:sw=4:et:
