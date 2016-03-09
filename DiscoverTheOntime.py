#! /usr/bin/env python

#
# DiscoverTheOntime.py --- Discover the ontime with users from ASA syslog
#
import os
import sys
import re
import itertools
import datetime
from optparse import OptionParser
import json

usage = "usage: %prog [options] 3> [unterminated log file]"

def fromISO8601ExtDateTime(text):
    sep = text.split ('+')
    if sep[1] != "09:00":
        raise ValueError, "This program only timezone +09:00"
    else:
        result = datetime.datetime.strptime (sep[0], "%Y-%m-%dT%H:%M:%S")
        return result

def extract_start_session_from_log(line, timeField, ipField, classField, messageField):
    result = {}
    result["terminate log"] = None
    result["line"]          = line
    #
    result["Message"]  = messageField
    result["Class"]    = classField
    result["DateTime"] = fromISO8601ExtDateTime (timeField)
    #
    matches = re.match (r'Group <(.*?)> User <(.*?)> IP <(.*?)>', messageField)
    result["Group"]    = matches.group(1)
    result["User"]     = matches.group(2)
    result["IP"]       = matches.group(3)
    return result

def extract_terminate_session_from_log(line, timeField, ipField, classField, messageField):
    result = {}
    result["start log"]     = None
    result["line"]          = line
    #
    result["Message"]  = messageField
    result["Class"]    = classField
    result["DateTime"] = fromISO8601ExtDateTime (timeField)
    #
    pattern = r'Group = (.*?), Username = (.*?), IP = (.*?), Session disconnected\. Session Type: (.*?), Duration: (.*?), '
    matches = re.match (pattern, messageField)
    result["Group"]         = matches.group(1)
    result["User"]          = matches.group(2)
    result["IP"]            = matches.group(3)
    result["SessionType"]   = matches.group(4)
    result["Duration"]      = matches.group(5)
    return result


#
# entry point
#
parser = OptionParser (usage)

parser.add_option(
    "-y", "--year",
    action="store",
    type="int",
    default= datetime.datetime.today ().year,
    dest="year",
    help="set year of log date, as default is this year."
)

(options, args) = parser.parse_args()

#
# main loop
#
start_session_logs = []
terminate_session_logs = []

for line in sys.stdin:
    m = re.match (r'([^ ]+) ?([^ ]+) ?(%ASA-[^:]+?-113039): (.*)$', line)
    if m:
        session = extract_start_session_from_log (line, m.group(1), m.group(2), m.group(3), m.group(4))
        start_session_logs.append (session)
    #
    m = re.match (r'([^ ]+) ?([^ ]+) ?(%ASA-[^:]+?-113019): (.*)$', line)
    if m:
        session = extract_terminate_session_from_log (line, m.group(1), m.group(2), m.group(3), m.group(4))
        terminate_session_logs.append (session)

#
# combine the relationship
#
for start in start_session_logs:
    term = next(itertools.ifilter(lambda it:it["DateTime"] >= start["DateTime"] and it["IP"] == start["IP"], terminate_session_logs), None)
    if term:
        start["terminate log"] = term
        term["start log"] = start

pipR, pipW = os.pipe ()
os.close (pipR)
os.dup2 (3, pipW)
unterminated_file = os.fdopen (pipW, "w")

for item in itertools.ifilter(lambda it:it["terminate log"] == None, start_session_logs):
    print >> unterminated_file, item["line"],
#
for item in itertools.ifilter(lambda it:it["start log"] == None, terminate_session_logs):
    print >> sys.stderr, "This record,"
    print >> sys.stderr, item["line"] ,
    print >> sys.stderr, " has no relationship!"

#
# To output
#
output_logs = []
for it in start_session_logs:
    if it["terminate log"]:
        container = {}
        container.update ({    "start_time": it["DateTime"]})
        container.update ({"terminate_time": it["terminate log"]["DateTime"]})
        container.update ({          "User": it["terminate log"]["User"]})
        container.update ({            "IP": it["terminate log"]["IP"]})
        container.update ({   "SessionType": it["terminate log"]["SessionType"]})
        container.update ({      "Duration": it["terminate log"]["Duration"]})
        output_logs.append (container)
 
def default_datetime(o):
    if isinstance(o, datetime.datetime):
        return o.isoformat()
    raise TypeError(repr(o) + " is not JSON serializable")

json.dump (output_logs, sys.stdout,
        ensure_ascii=True,
        check_circular=True,
        separators=None,
        encoding='utf-8',
        default=default_datetime,
        sort_keys=False,
        indent=4)

