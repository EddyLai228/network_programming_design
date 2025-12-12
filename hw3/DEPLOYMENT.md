# Server Deployment Guide

本文件說明如何將 Game Store System 部署到 Linux 伺服器上。

## 環境需求

- Linux 系統 (Ubuntu 18.04+ / CentOS 7+ / Debian 10+)
- Python 3.7 或更高版本
- 網路連線
- 開放防火牆 Port: 8001, 8002

## 部署步驟

### 1. 準備伺服器

```bash
# 更新系統
sudo apt update && sudo apt upgrade -y  # Ubuntu/Debian
# 或
sudo yum update -y  # CentOS

# 安裝 Python 3 (如果尚未安裝)
sudo apt install python3 python3-pip -y  # Ubuntu/Debian
# 或
sudo yum install python3 python3-pip -y  # CentOS

# 檢查 Python 版本
python3 --version
```

### 2. 上傳程式碼

#### 方法 A: 使用 Git

```bash
# 在伺服器上
cd ~
git clone <your-github-repo-url>
cd network_progarmming_design/hw3
```

#### 方法 B: 使用 SCP

```bash
# 在本地機器上
scp -r hw3 user@server-ip:~/
```

### 3. 設定防火牆

```bash
# Ubuntu/Debian (使用 ufw)
sudo ufw allow 8001/tcp
sudo ufw allow 8002/tcp
sudo ufw reload

# CentOS (使用 firewalld)
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --permanent --add-port=8002/tcp
sudo firewall-cmd --reload
```

### 4. 配置伺服器

編輯伺服器設定（如果需要綁定到特定 IP）:

```bash
cd hw3/server

# 編輯 developer_server.py
# 修改 host='0.0.0.0' 為你想綁定的 IP (或保持 0.0.0.0 接受所有連線)

# 編輯 lobby_server.py
# 同上
```

### 5. 測試本地連線

```bash
cd hw3/server

# 啟動 Developer Server
python3 developer_server.py
# 應該看到: Developer Server started on 0.0.0.0:8001

# 在另一個終端啟動 Lobby Server
python3 lobby_server.py
# 應該看到: Lobby Server started on 0.0.0.0:8002
```

按 `Ctrl+C` 停止測試。

### 6. 使用 systemd 設定自動啟動 (推薦)

#### 建立 Developer Server 服務

```bash
sudo nano /etc/systemd/system/gamestore-dev.service
```

內容:
```ini
[Unit]
Description=Game Store Developer Server
After=network.target

[Service]
Type=simple
User=<your-username>
WorkingDirectory=/home/<your-username>/hw3/server
ExecStart=/usr/bin/python3 /home/<your-username>/hw3/server/developer_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 建立 Lobby Server 服務

```bash
sudo nano /etc/systemd/system/gamestore-lobby.service
```

內容:
```ini
[Unit]
Description=Game Store Lobby Server
After=network.target

[Service]
Type=simple
User=<your-username>
WorkingDirectory=/home/<your-username>/hw3/server
ExecStart=/usr/bin/python3 /home/<your-username>/hw3/server/lobby_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 啟動服務

```bash
# 重新載入 systemd
sudo systemctl daemon-reload

# 啟動服務
sudo systemctl start gamestore-dev
sudo systemctl start gamestore-lobby

# 設定開機自動啟動
sudo systemctl enable gamestore-dev
sudo systemctl enable gamestore-lobby

# 檢查狀態
sudo systemctl status gamestore-dev
sudo systemctl status gamestore-lobby
```

### 7. 檢視日誌

```bash
# 即時查看 Developer Server 日誌
sudo journalctl -u gamestore-dev -f

# 即時查看 Lobby Server 日誌
sudo journalctl -u gamestore-lobby -f

# 查看最近的日誌
sudo journalctl -u gamestore-dev -n 50
sudo journalctl -u gamestore-lobby -n 50
```

### 8. 管理服務

```bash
# 停止服務
sudo systemctl stop gamestore-dev
sudo systemctl stop gamestore-lobby

# 重啟服務
sudo systemctl restart gamestore-dev
sudo systemctl restart gamestore-lobby

# 停用開機自動啟動
sudo systemctl disable gamestore-dev
sudo systemctl disable gamestore-lobby
```

## 替代方案: 使用 screen 或 tmux

如果不想使用 systemd，可以使用 screen 或 tmux:

### 使用 screen

```bash
# 安裝 screen
sudo apt install screen -y  # Ubuntu/Debian

# 啟動 Developer Server
screen -dmS dev-server bash -c 'cd ~/hw3/server && python3 developer_server.py'

# 啟動 Lobby Server
screen -dmS lobby-server bash -c 'cd ~/hw3/server && python3 lobby_server.py'

# 查看運行中的 screen
screen -ls

# 連接到 screen
screen -r dev-server

# 離開 screen (不停止): Ctrl+A, D
```

### 使用 tmux

```bash
# 安裝 tmux
sudo apt install tmux -y

# 建立新 session
tmux new -s gamestore

# 在 tmux 中啟動第一個伺服器
cd ~/hw3/server
python3 developer_server.py

# 開新視窗: Ctrl+B, C
python3 lobby_server.py

# 離開 tmux (不停止): Ctrl+B, D

# 重新連接
tmux attach -t gamestore
```

## 測試部署

### 從本地測試連線

```bash
# 在你的本地機器上
cd hw3/developer
./start_developer.sh <server-ip> 8001

# 測試註冊和登入
```

## 維護

### 備份資料

```bash
# 定期備份資料庫
cd ~/hw3/server
tar -czf backup-$(date +%Y%m%d).tar.gz data/ uploaded_games/
```

### 清理資料

```bash
# Demo 前清理測試資料
cd ~/hw3/server
./clear_data.sh
```

### 監控

```bash
# 檢查伺服器是否運行
netstat -tulpn | grep :8001
netstat -tulpn | grep :8002

# 或使用 ss
ss -tulpn | grep :8001
ss -tulpn | grep :8002
```

## 安全建議

1. **使用防火牆**: 只開放必要的 Port
2. **定期更新**: 保持系統和 Python 更新
3. **限制存取**: 使用 IP 白名單（如果需要）
4. **備份資料**: 定期備份 `data/` 和 `uploaded_games/`
5. **日誌監控**: 定期檢查日誌檔案

## 故障排除

### 問題: Port 被佔用

```bash
# 找出佔用 Port 的程序
sudo lsof -i :8001
sudo lsof -i :8002

# 結束程序
sudo kill -9 <PID>
```

### 問題: 權限錯誤

```bash
# 確認檔案權限
ls -la ~/hw3/server

# 修正權限
chmod +x ~/hw3/server/*.sh
chmod 755 ~/hw3/server/*.py
```

### 問題: Python 模組缺失

```bash
# 雖然本系統不需要額外模組，但如果有需要:
pip3 install -r requirements.txt
```

### 問題: 連線逾時

- 檢查防火牆設定
- 確認伺服器正在運行
- 測試網路連線: `ping <server-ip>`
- 測試 Port: `telnet <server-ip> 8001`

## 效能調整

### 增加連線數限制

編輯伺服器程式:

```python
# 在 developer_server.py 和 lobby_server.py 中
self.server_socket.listen(5)  # 改為更大的值，例如 100
```

### 使用更快的序列化

如果效能成為問題，可以考慮:
- 使用 msgpack 取代 JSON
- 實作壓縮傳輸
- 使用連線池

## 監控腳本

建立一個簡單的監控腳本:

```bash
#!/bin/bash
# monitor.sh

while true; do
    if ! pgrep -f "developer_server.py" > /dev/null; then
        echo "Developer server is down! Restarting..."
        cd ~/hw3/server && python3 developer_server.py &
    fi
    
    if ! pgrep -f "lobby_server.py" > /dev/null; then
        echo "Lobby server is down! Restarting..."
        cd ~/hw3/server && python3 lobby_server.py &
    fi
    
    sleep 60
done
```

## 聯絡資訊

如有部署問題，請聯絡系統管理員。
