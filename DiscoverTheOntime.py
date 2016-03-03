#! /usr/bin/env python

#
# DiscoverTheOntime.py --- Discover the ontime with users from switch log
#
import os
import sys
import re
import itertools
from datetime import datetime as dt
from optparse import OptionParser

usage = "usage: %prog [options] keyword"


def extract_start_session_from_log(line, year):
    sep = line.rstrip().split (': ')
    result = {}
    result["terminate log"] = None
    result["line"]          = line
    #
    result["Message"]  = sep[2]
    result["Class"]    = sep[1]
    result["DateTime"] = dt.strptime (sep[0], "%b %d %H:%M:%S %Z").replace (year)
    #
    matches = re.match (r'Group <(.*?)> User <(.*?)> IP <(.*?)>', sep[2])
    result["Group"]    = matches.group(1)
    result["User"]     = matches.group(2)
    result["IP"]       = matches.group(3)
    return result

def extract_terminate_session_from_log(line, year):
    sep = line.rstrip().split (': ')
    result = {}
    result["start log"]     = None
    result["line"]          = line
    #
    result["Message"]  = ': '.join (sep[2:])
    result["Class"]    = sep[1]
    result["DateTime"] = dt.strptime (sep[0], "%b %d %H:%M:%S %Z").replace (year)
    #
    matches = re.match (r'Group = (.*?), Username = (.*?), IP = (.*?), Session disconnected\. Session Type: (.*?), Duration: (.*?), ', result["Message"])
    result["Group"]         = matches.group(1)
    result["User"]          = matches.group(2)
    result["IP"]            = matches.group(3)
    result["SessionType"]   = matches.group(4)
    result["Duration"]      = matches.group(5)
    return result

#
#
#
parser = OptionParser (usage)

parser.add_option(
    "-y", "--year",
    action="store",
    type="int",
    default= dt.today ().year,
    dest="year",
    help="set year of log date, as default is this year."
)

(options, args) = parser.parse_args()

start_session_logs = []
terminate_session_logs = []

for line in sys.stdin:
    if re.search (r'%ASA-[^:]+?-113039:', line):
        start_session_logs.append (
                extract_start_session_from_log (line, options.year))
    #
    if re.search (r'%ASA-[^:]+?-113019:', line):
        terminate_session_logs.append (
                extract_terminate_session_from_log (line, options.year))

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
    print >> unterminated_file, item["line"]
for item in itertools.ifilter(lambda it:it["start log"] == None, terminate_session_logs):
    print >> sys.stderr, "This record,"
    print >> sys.stderr, item["line"] ,
    print >> sys.stderr, " has no relationship!"

buf = []
for num, item in enumerate (start_session_logs):
    st = item
    tm = item["terminate log"]
    text = "[ '{0}', '{1}'".format (1+num, st["User"])
    text = text + ", new Date({0})".format (st["DateTime"].strftime ('%Y, %m, %d, %H, %M, %S'))
    if tm:
        text = text + ", new Date({0})".format (tm["DateTime"].strftime ('%Y, %m, %d, %H, %M, %S'))
        text = text + "],"
        buf.append (text)

if buf:
    buf[-1] = buf[-1].rstrip(',')

#print start_and_term_relationship

datarows = "\n            ".join (buf)

#
#
#
html = """
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<script type="text/javascript" src="https://www.google.com/jsapi"></script>
<script type="text/javascript">
    google.load('visualization', '1', {{'packages':['timeline']}});
    google.setOnLoadCallback(drawChart);

    function drawChart() {{
        var data = new google.visualization.DataTable();
        data.addColumn({{ type: 'string', id: 'Number' }});
        data.addColumn({{ type: 'string', id: 'Name' }});
        data.addColumn({{ type: 'date', id: 'Start' }});
        data.addColumn({{ type: 'date', id: 'End' }});
        data.addRows([
            {0}
        ]);

        var chart = new google.visualization.Timeline(document.getElementById('chart_div'));

        var options = {{
            timeline: {{
                showRowLabels: false,
            }}
        }};

        chart.draw(data, options);
      }}
</script>
</head>
<body>
    <div id="chart_div" style="height:100%"></div>
</body>
</html>
"""[1:-1]

print html.format(datarows)
