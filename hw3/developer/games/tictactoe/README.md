# Tic-Tac-Toe

經典的井字遊戲（三連棋）

## 遊戲規則

- 兩位玩家輪流在3x3的格子上放置自己的符號（X或O）
- 先在橫向、縱向或斜向連成一線者獲勝
- 如果格子填滿仍無人獲勝，則為平局

## 如何遊玩

### 啟動伺服器
```bash
python game.py server
```

### 啟動客戶端（玩家）
```bash
# 玩家1
python game.py client --host localhost

# 玩家2（在另一個終端機）
python game.py client --host localhost
```

### 操作方式
- 輸入座標格式: `row col` (例如: `0 1`)
- 座標範圍: 0-2

## 範例

```
  0   1   2
0 X |   | O
  -----------
1   | X |  
  -----------
2 O |   | X
```

玩家X輸入 `1 1` 在中央放置符號
