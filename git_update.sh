#!/bin/bash
cp -frp crysadm crysadm.old
cd 2
git clone https://github.com/evil972/yjg.git
rm crysadm/crysadm/config.py
cp -frp crysadm/crysadm/* ../crysadm/
../run.sh
rm -rf *
