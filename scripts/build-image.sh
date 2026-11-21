#!/bin/sh
set -eu
: "${IB_DIR:?Set IB_DIR to OpenWrt ImageBuilder directory}"
cd "$IB_DIR"
make image PROFILE="generic" PACKAGES="luci luci-ssl openssh-server sqlite3 curl wget ca-bundle ip-full tcpdump-mini ethtool" FILES="$PWD/files" || make image PROFILE="generic" PACKAGES="luci luci-ssl sqlite3 curl wget ca-bundle ip-full tcpdump-mini ethtool" 
