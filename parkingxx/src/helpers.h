#ifndef _PARKINGXX__HELPERS_H_
#define _PARKINGXX__HELPERS_H_

#include <cstdio>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <util/nlogger.h>
#include <util/element_tree.h>
#include <orm/data_object.h>
#include "micro_http.h"
#include "app_class.h"

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

inline Yb::ElementTree::ElementPtr mk_resp(const Yb::String &status,
        const Yb::String &status_code = _T(""))
{
    Yb::ElementTree::ElementPtr res(Yb::ElementTree::new_json_dict());
    res->add_json_string(_T("status"), status);
    if (!Yb::str_empty(status_code))
        res->add_json_string(_T("status_code"), status_code);
    char buf[40];
    Yb::MilliSec t = Yb::get_cur_time_millisec();
    std::sprintf(buf, "%u.%03u", (unsigned)(t/1000), (unsigned)(t%1000));
    res->add_json(_T("ts"), WIDEN(buf));
    return res;
}

class ApiResult: public std::runtime_error
{
    Yb::ElementTree::ElementPtr p_;
public:
    ApiResult(Yb::ElementTree::ElementPtr p)
        : runtime_error("api result"), p_(p)
    {}
    virtual ~ApiResult() throw () {}
    Yb::ElementTree::ElementPtr result() const { return p_; }
};

const std::string money2str(const Yb::Decimal &x);
const std::string timestamp2str(double ts);
double datetime2timestamp(const Yb::DateTime &d);
double datetime_diff(const Yb::DateTime &a, const Yb::DateTime &b);
const std::string dict2str(const Yb::StringDict &params);
const Yb::StringDict json2dict(const std::string &json_str);
void randomize();

template <class HttpHandler>
int run_server_app(const std::string &log_name, const std::string &db_name,
        int port, HttpHandler *handlers_array, int n_handlers,
        const std::string &error_content_type,
        const std::string &error_body,
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
        typedef HttpServer<HttpHandler> MyHttpServer;
        typename MyHttpServer::HandlerMap handlers;
        for (int i = 0; i < n_handlers; ++i)
            handlers[prefix + handlers_array[i].name()] = handlers_array[i];
        MyHttpServer server(
                port, handlers, &theApp::instance(),
                error_content_type, error_body);
        server.serve();
    }
    catch (const std::exception &ex) {
        log->error(std::string("exception: ") + ex.what());
        return 1;
    }
    return 0;
}

typedef Yb::ElementTree::ElementPtr (*JsonHttpHandler)(
        Yb::Session &session, Yb::ILogger &logger,
        const Yb::StringDict &params);

class JsonHttpWrapper
{
    Yb::String name_, default_status_;
    JsonHttpHandler f_;

    std::string dump_result(Yb::ILogger &logger, Yb::ElementTree::ElementPtr res)
    {
        std::string res_str = etree2json(res);
        //std::string res_str = res->serialize();
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

    const HttpHeaders operator() (const HttpHeaders &request)
    {
        Yb::ILogger::Ptr logger(theApp::instance().new_logger(NARROW(name_)));
        TimerGuard t(*logger);
        try {
            const Yb::StringDict &params = request.get_params();
            logger->info("started path: " + NARROW(request.get_path())
                         + ", params: " + dict2str(params));
            int version = params.get_as<int>("version");
            YB_ASSERT(version >= 2);
            std::auto_ptr<Yb::Session> session(
                    theApp::instance().new_session());
            Yb::ElementTree::ElementPtr res = f_(*session, *logger, params);
            session->commit();
            HttpHeaders response(10, 200, _T("OK"));
            response.set_response_body(dump_result(*logger, res), _T("text/json"));
            t.set_ok();
            return response;
        }
        catch (const ApiResult &ex) {
            t.set_ok();
            HttpHeaders response(10, 200, _T("OK"));
            response.set_response_body(dump_result(*logger, ex.result()), _T("text/json"));
            return response;
        }
        catch (const std::exception &ex) {
            logger->error(std::string("exception: ") + ex.what());
            HttpHeaders response(10, 500, _T("Internal error"));
            response.set_response_body(dump_result(*logger, mk_resp(default_status_)), _T("text/json"));
            return response;
        }
        catch (...) {
            logger->error("unknown exception");
            HttpHeaders response(10, 500, _T("Internal error"));
            response.set_response_body(dump_result(*logger, mk_resp(default_status_)), _T("text/json"));
            return response;
        }
    }
};

#define WRAP(func) JsonHttpWrapper(_T(#func), func)

#endif // _PARKINGXX__HELPERS_H_
// vim:ts=4:sts=4:sw=4:et:
