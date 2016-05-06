#!/bin/bash
cp -frp crysadm crysadm.old
cd tmp
git clone https://github.com/evil972/yjg.git
rm /yjg/tmp/yjg/crysadm/config.py
cp -frp yjg/tmp/yjg/crysadm/* /yjg/
/yjg/run.sh
rm -rf *
