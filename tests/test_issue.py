import sys
import urllib

def run(ntimes, url):
    for i in xrange(ntimes):
        f = urllib.urlopen(url)
        s = f.read()
        print s
        f.close()

if len(sys.argv) != 3:
    print "Run like this: %s 10 " \
        "'http://localhost:8112/parking/issue_ticket?parking_id=15001&version=2'" \
        % (sys.argv[0],)
else:
    run(int(sys.argv[1]), sys.argv[2])
