#include "helpers.h"
#include <util/string_utils.h>

using namespace std;
using namespace Yb;

const string money2str(const Decimal &x)
{
    ostringstream out;
    out << setprecision(2) << x;
    return out.str();
}

const string timestamp2str(double ts)
{
    ostringstream out;
    out << fixed << setprecision(3) << ts;
    return out.str();
}

double datetime2timestamp(const DateTime &d)
{
    tm t = boost::posix_time::to_tm(d);
    return (unsigned)mktime(&t);
}

double datetime_diff(const DateTime &a, const DateTime &b)
{
    boost::posix_time::time_duration td = b - a;
    return td.total_seconds();
}

const string dict2str(const StringDict &params)
{
    using namespace StrUtils;
    ostringstream out;
    out << "{";
    StringDict::const_iterator it = params.begin(), end = params.end();
    for (bool first = true; it != end; ++it, first = false) {
        if (!first)
            out << ", ";
        out << it->first << ": " << dquote(c_string_escape(it->second));
    }
    out << "}";
    return out.str();
}

void randomize()
{
    srand(get_cur_time_millisec() % 1000000000);
    rand();
    rand();
}

// vim:ts=4:sts=4:sw=4:et:
