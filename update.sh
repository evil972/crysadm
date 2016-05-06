#!/bin/bash
cp -frp crysadm crysadm.old
cd tmp
git clone https://github.com/evil972/yjg.git
rm crysadm/crysadm/config.py
cp -frp yjg/tmp/crysadm/* ../yjg/
../run.sh
rm -rf *
