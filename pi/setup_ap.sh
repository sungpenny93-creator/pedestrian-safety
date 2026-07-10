#!/bin/bash

# Configuration
SSID="OneStepAhead_AP"
PASSWORD="PennySafety@2026"
IP_ADDR="192.168.4.1/24"

echo "=========================================="
echo "  One Step Ahead: Pi AP Setup Script      "
echo "=========================================="

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

echo "[1/4] Checking for NetworkManager..."
if ! command -v nmcli &> /dev/null; then
    echo "Error: nmcli not found. Please install NetworkManager."
    exit 1
fi

echo "[2/4] Creating Wi-Fi Hotspot: $SSID..."
# Delete existing connection if any
nmcli con delete "$SSID" &> /dev/null

# Create new AP connection
nmcli con add type wifi ifname wlan0 mode ap con-name "$SSID" ssid "$SSID"
nmcli con modify "$SSID" wifi-sec.key-mgmt wpa-psk
nmcli con modify "$SSID" wifi-sec.psk "$PASSWORD"
nmcli con modify "$SSID" ipv4.method shared ipv4.addresses "$IP_ADDR"
# 根據您過去成功的紀錄，這是一次性套用所有最嚴格的 ESP32 相容設定：
# 1. 強制設定為 2.4GHz 頻段，並鎖定為頻道 1
nmcli con modify "$SSID" 802-11-wireless.band bg 802-11-wireless.channel 1
# 2. 強制使用 WPA2 (RSN) 與 AES (CCMP) 加密，排除任何 WPA3 的混淆
nmcli con modify "$SSID" 802-11-wireless-security.proto rsn 802-11-wireless-security.pairwise ccmp 802-11-wireless-security.group ccmp
# 3. 關閉 PMF (Protected Management Frames)
nmcli con modify "$SSID" wifi-sec.pmf 1
# 4. 關閉 Wi-Fi 休眠省電模式 (powersave 2 代表關閉)，避免熱點不穩定
nmcli con modify "$SSID" 802-11-wireless.powersave 2
# 5. 防止 NetworkManager 擅自更換 MAC 位址導致連線中斷
nmcli con modify "$SSID" wifi.cloned-mac-address preserve

echo "[3/4] Starting AP..."
nmcli con up "$SSID"

echo "[4/4] Setup Complete!"
echo "------------------------------------------"
echo "SSID:     $SSID"
echo "Password: $PASSWORD"
echo "Pi IP:    192.168.4.1"
echo "------------------------------------------"
echo "Note: Your ESP32-CAMs should now connect to this network."
