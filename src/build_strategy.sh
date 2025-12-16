#!/bin/bash

cd /student_work/kyahata2/ss/bt/utilities
./StrategyCommandLine cmd create_instance OFIStrategy4 OFIStrategy UIUC SIM-1001-101 dlariviere 1000000 -symbols "DIA|UNH|GS|HD|MSFT|CRM|MCD|HON|BA|V|AMGN|CAT|MMM|NKE|AXP|DIS|JPM|JNJ|TRV|AAPL|WMT|PG|IBM|CVX|MRK|DOW|CSCO|KO|VZ|INTC|WBA|KD"
./StrategyCommandLine cmd strategy_instance_list
./StrategyCommandLine cmd quit





