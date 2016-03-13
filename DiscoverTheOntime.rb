#! /usr/bin/env ruby
#
# DiscoverTheOntime.rb --- Discover the ontime with users from ASA syslog
#
require 'time'

#開始ログ行
re_start_line = /
    (\S+)                          #1 ISOフォーマットの時間
    [^%]+?                         #  現在無視するフィールド
    (%ASA-[^:]+?-113039):          #2 %ASA-6-113039
    \ Group\ <(.*?)>               #3 Group
    \ User\ <(.*?)>                #4 User
    \ IP\ <(.*?)>                  #5 IP
    \ (.*)$                        #6 食い残し
/x

#終了ログ行
re_term_line = /
    (\S+)                          #1 ISOフォーマットの時間
    [^%]+?                         #  現在無視するフィールド
    (%ASA-[^:]+?-113019):          #2 %ASA-4-113019
    \ Group\ =\ (.*?),             #3 Group
    \ Username\ =\ (.*?),          #4 Username
    \ IP\ =\ (.*?),                #5 IP
    \ Session\ disconnected\.
    \ Session\ Type:\ (.*?),       #6 Session Type
    \ Duration:\ (.*?),            #7 Duration
    \ (.*)$                        #8 食い残し
/x

start_session_logs = []
terminate_session_logs = []

#
# log file format error
#
class LogFileFormatError < StandardError; end

#
# main loop
#
STDIN.each_line do |line|
    begin
        if line.include?('-113039:') then
            #開始ログ行を取り出す
            m = re_start_line.match(line) or
                raise LogFileFormatError, "L##{STDIN.lineno} - Sorry, unsupported log format."
            start_session_logs.push({
                :TerminateLog => nil,
                        :Line => line,
                    :DateTime => Time.iso8601(m[1]),
                       :Class => m[2],
                       :Group => m[3],
                        :User => m[4],
                          :IP => m[5],
                    :Leftover => m[6],
            })
        elsif line.include?('-113019:') then
            #終了ログ行を取り出す
            m = re_term_line.match(line) or
                raise LogFileFormatError, "L##{STDIN.lineno} - Sorry, unsupported log format."
            terminate_session_logs.push({
                :StartLog => nil,
                    :Line => line,
                :DateTime => Time.iso8601(m[1]),
                   :Class => m[2],
                   :Group => m[3],
                    :User => m[4],
                      :IP => m[5],
             :SessionType => m[6],
                :Duration => m[7],
                :Leftover => m[8],
            })
        end
    rescue LogFileFormatError => ex
        STDERR.puts ex
    end
end

#
# combine the relationship
#
start_session_logs.each do |start|
    term = terminate_session_logs.find {|it| it[:DateTime] >= start[:DateTime] and it[:IP] === start[:IP]}
    unless term.nil? then
        start[:TerminateLog] = term
        term[:StartLog] = start
    end
end

IO.open( 3, mode="w" ) do |out|
    nopair = start_session_logs.select {|it| it[:TerminateLog].nil?}
    nopair.each do |item|
        out.print item[:Line]
    end
end

nopair = terminate_session_logs.select {|it| it[:StartLog].nil?}
nopair.each do |item|
    STDERR.puts "This record,"
    STDERR.print item[:Line]
    STDERR.puts " has no relationship!"
end

#
# To output
#
buf = []
start_session_logs.each do |item|
    numb = buf.length
    st = item
    tm = item[:TerminateLog]
    unless tm.nil? then
        stime = st[:DateTime].getlocal.strftime('%Y, %m, %d, %H, %M, %S')
        ttime = tm[:DateTime].getlocal.strftime('%Y, %m, %d, %H, %M, %S')
        buf.push("[ '#{numb+1}', '#{st[:User]}', new Date(#{stime}), new Date(#{ttime})],")
    end
end
datarows = buf.join("\n            ")

#
#
#
text = <<"EOS"
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
<script type="text/javascript" src="https://www.google.com/jsapi"></script>
<script type="text/javascript">
    google.load('visualization', '1', {'packages':['timeline']});
    google.setOnLoadCallback(drawChart);

    function drawChart() {
        var data = new google.visualization.DataTable();
        data.addColumn({ type: 'string', id: 'Number' });
        data.addColumn({ type: 'string', id: 'Name' });
        data.addColumn({ type: 'date', id: 'Start' });
        data.addColumn({ type: 'date', id: 'End' });
        data.addRows([
            #{datarows}
        ]);

        var chart = new google.visualization.Timeline(document.getElementById('chart_div'));

        var options = {
            timeline: {
                showRowLabels: false,
            }
        };

        chart.draw(data, options);
      }
</script>
</head>
<body>
    <div id="chart_div" style="height:100%"></div>
</body>
</html>
EOS
print text unless buf.empty?
