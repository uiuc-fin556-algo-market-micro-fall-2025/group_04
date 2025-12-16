#!/bin/bash

startDate='2019-09-13'
endDate='2019-09-13'
instanceName='OFIStrategy1'

(cd /student_work/kyahata2/ss/bt && ./StrategyServerBacktesting&)

echo "Sleeping for 2 seconds while waiting for strategy studio to boot"
sleep 2

# Start the backtest
(cd /student_work/kyahata2/ss/bt/utilities/ && ./StrategyCommandLine cmd start_backtest $startDate $endDate $instanceName 0)


# Get the line number which ends with finished.
foundFinishedLogFile=$(grep -nr "finished.$" /student_work/kyahata2/ss/bt/logs/main_log.txt | gawk '{print $1}' FS=":"|tail -1)

# DEBUGGING OUTPUT
echo "Last line found:",$foundFinishedLogFile

# If the line ending with finished. is less than the previous length of the log file, then strategyBacktesting has not finished,
# once its greater than the previous, it means it has finished.
while ((logFileNumLines > foundFinishedLogFile))
do
    foundFinishedLogFile=$(grep -nr "finished.$" /student_work/kyahata2/ss/bt/logs/main_log.txt | gawk '{print $1}' FS=":"|tail -1)

    #DEBUGGING OUTPUT
    echo "Waiting for strategy to finish"
    sleep 1
done

echo "Sleeping for 10 seconds..."

sleep 10

echo "run_backtest.sh: Strategy Studio finished backtesting"


