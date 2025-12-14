"""
Blackjack (21點) - CLI Multiplayer Game
A poker game for 3-6 players
"""

import socket
import json
import sys
import os
import random
import time
import threading
from collections import deque

# 牌組定義
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
VALUES = {
    'A': 11, '2': 2, '3': 3, '4': 4, '5': 5,
    '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10
}


class BlackjackGame:
    def __init__(self, player_count):
        self.player_count = player_count
        self.players = {}  # username -> {chips, bet, hand, status}
        self.dealer_hand = []
        self.deck = []
        self.current_player_index = 0
        self.player_order = []
        self.round = 0
        self.phase = 'waiting'  # waiting, betting, playing, dealer, ended
        self.game_over = False
        self.winners = []
        
    def init_players(self, usernames):
        """初始化玩家"""
        self.player_order = usernames
        for username in usernames:
            self.players[username] = {
                'chips': 1000,
                'bet': 0,
                'hand': [],
                'status': 'waiting',  # waiting, playing, stand, bust, blackjack, win, lose, tie
                'can_double': False
            }
    
    def create_deck(self):
        """創建並洗牌"""
        deck = []
        for suit in SUITS:
            for rank in RANKS:
                deck.append({'suit': suit, 'rank': rank})
        random.shuffle(deck)
        return deck
    
    def calculate_hand(self, hand):
        """計算手牌點數"""
        total = 0
        aces = 0
        
        for card in hand:
            total += VALUES[card['rank']]
            if card['rank'] == 'A':
                aces += 1
        
        # 調整A的值
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        return total
    
    def card_to_string(self, card):
        """將卡牌轉換為字符串"""
        return f"{card['rank']}{card['suit']}"
    
    def hand_to_string(self, hand):
        """將手牌轉換為字符串"""
        return ', '.join([self.card_to_string(card) for card in hand])
    
    def start_new_round(self):
        """開始新一局"""
        self.round += 1
        self.phase = 'betting'
        self.deck = self.create_deck()
        self.dealer_hand = []
        self.current_player_index = 0
        
        # 重置玩家狀態
        for username in self.player_order:
            player = self.players[username]
            player['hand'] = []
            player['bet'] = 0
            player['status'] = 'waiting'
            player['can_double'] = False
    
    def deal_initial_cards(self):
        """發初始牌"""
        # 每個玩家兩張牌
        for username in self.player_order:
            player = self.players[username]
            if player['bet'] > 0:
                player['hand'].append(self.deck.pop())
                player['hand'].append(self.deck.pop())
                player['status'] = 'playing'
        
        # 莊家兩張牌
        self.dealer_hand.append(self.deck.pop())
        self.dealer_hand.append(self.deck.pop())
    
    def check_blackjacks(self):
        """檢查初始Blackjack"""
        dealer_score = self.calculate_hand(self.dealer_hand)
        dealer_has_blackjack = (dealer_score == 21)
        
        for username in self.player_order:
            player = self.players[username]
            if player['bet'] == 0:
                continue
            
            player_score = self.calculate_hand(player['hand'])
            player_has_blackjack = (player_score == 21)
            
            if player_has_blackjack and dealer_has_blackjack:
                player['status'] = 'tie'
                player['chips'] += player['bet']
            elif player_has_blackjack:
                player['status'] = 'blackjack'
                player['chips'] += int(player['bet'] * 2.5)
            elif dealer_has_blackjack:
                player['status'] = 'lose'
    
    def get_current_player(self):
        """獲取當前玩家"""
        while self.current_player_index < len(self.player_order):
            username = self.player_order[self.current_player_index]
            player = self.players[username]
            if player['status'] == 'playing':
                return username
            self.current_player_index += 1
        return None
    
    def player_hit(self, username):
        """玩家要牌"""
        player = self.players[username]
        card = self.deck.pop()
        player['hand'].append(card)
        player['can_double'] = False
        
        score = self.calculate_hand(player['hand'])
        if score > 21:
            player['status'] = 'bust'
            return 'bust', score
        elif score == 21:
            player['status'] = 'stand'
            return 'stand', score
        return 'continue', score
    
    def player_stand(self, username):
        """玩家停牌"""
        player = self.players[username]
        player['status'] = 'stand'
        player['can_double'] = False
    
    def player_double(self, username):
        """玩家加倍"""
        player = self.players[username]
        if not player['can_double'] or player['bet'] > player['chips']:
            return False, "無法加倍"
        
        player['chips'] -= player['bet']
        player['bet'] *= 2
        player['can_double'] = False
        
        # 只能再拿一張牌
        card = self.deck.pop()
        player['hand'].append(card)
        
        score = self.calculate_hand(player['hand'])
        if score > 21:
            player['status'] = 'bust'
        else:
            player['status'] = 'stand'
        
        return True, score
    
    def dealer_play(self):
        """莊家補牌"""
        self.phase = 'dealer'
        dealer_score = self.calculate_hand(self.dealer_hand)
        
        while dealer_score < 17:
            card = self.deck.pop()
            self.dealer_hand.append(card)
            dealer_score = self.calculate_hand(self.dealer_hand)
        
        return dealer_score
    
    def determine_winners(self):
        """判斷勝負"""
        dealer_score = self.calculate_hand(self.dealer_hand)
        
        for username in self.player_order:
            player = self.players[username]
            
            if player['bet'] == 0:
                continue
            if player['status'] in ['blackjack', 'tie', 'bust', 'lose']:
                continue
            
            player_score = self.calculate_hand(player['hand'])
            
            if dealer_score > 21:
                # 莊家爆牌
                player['status'] = 'win'
                player['chips'] += player['bet'] * 2
            elif player_score > dealer_score:
                player['status'] = 'win'
                player['chips'] += player['bet'] * 2
            elif player_score < dealer_score:
                player['status'] = 'lose'
            else:
                player['status'] = 'tie'
                player['chips'] += player['bet']
    
    def get_game_state(self):
        """獲取遊戲狀態"""
        return {
            'round': self.round,
            'phase': self.phase,
            'dealer_hand': self.dealer_hand,
            'players': {username: {
                'chips': self.players[username]['chips'],
                'bet': self.players[username]['bet'],
                'hand': self.players[username]['hand'],
                'status': self.players[username]['status'],
                'can_double': self.players[username]['can_double']
            } for username in self.player_order},
            'current_player': self.player_order[self.current_player_index] if self.current_player_index < len(self.player_order) else None
        }


class BlackjackServer:
    def __init__(self, host='0.0.0.0', port=5001):
        self.host = host
        self.port = port
        self.clients = {}  # socket -> username
        self.game = None
        self.lock = threading.Lock()
        self.min_players = 3
        self.max_players = 6
        self.waiting_time = 5
        
    def start(self):
        """啟動服務器"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(self.max_players)
        
        print(f"♠♥♦♣ Blackjack Server started on {self.host}:{self.port} ♠♥♦♣")
        print(f"等待玩家加入... (最少{self.min_players}人, 最多{self.max_players}人)")
        
        # 等待玩家加入
        self.wait_for_players(server_socket)
        
        # 開始遊戲
        self.run_game()
        
        # 清理
        for sock in self.clients.keys():
            sock.close()
        server_socket.close()
    
    def wait_for_players(self, server_socket):
        """等待玩家加入"""
        server_socket.settimeout(1.0)
        start_time = time.time()
        
        while len(self.clients) < self.max_players:
            try:
                client_socket, address = server_socket.accept()
                
                # 接收玩家名稱
                data = self.recv_message(client_socket)
                if data and data['type'] == 'join':
                    username = data['username']
                    self.clients[client_socket] = username
                    print(f"玩家 {username} 已加入 ({len(self.clients)}/{self.max_players})")
                    
                    # 發送歡迎消息
                    self.send_message(client_socket, {
                        'type': 'welcome',
                        'message': f'歡迎 {username}！等待其他玩家...'
                    })
                    
                    # 達到最少人數，開始倒計時
                    if len(self.clients) >= self.min_players:
                        elapsed = time.time() - start_time
                        if elapsed < self.waiting_time:
                            print(f"已達最少人數，{self.waiting_time - int(elapsed)}秒後開始遊戲...")
                        else:
                            break
                    
            except socket.timeout:
                if len(self.clients) >= self.min_players:
                    elapsed = time.time() - start_time
                    if elapsed >= self.waiting_time:
                        break
                continue
        
        if len(self.clients) < self.min_players:
            print("人數不足，遊戲結束")
            for sock in self.clients.keys():
                self.send_message(sock, {
                    'type': 'error',
                    'message': '人數不足，遊戲結束'
                })
            sys.exit(0)
        
        print(f"\n遊戲開始！共 {len(self.clients)} 位玩家")
        usernames = list(self.clients.values())
        self.game = BlackjackGame(len(usernames))
        self.game.init_players(usernames)
    
    def run_game(self):
        """運行遊戲主循環"""
        while True:
            # 開始新一局
            self.game.start_new_round()
            self.broadcast({
                'type': 'new_round',
                'round': self.game.round,
                'message': f'\n{"="*50}\n第 {self.game.round} 局開始！\n{"="*50}'
            })
            
            # 下注階段
            self.betting_phase()
            
            # 發初始牌
            self.game.deal_initial_cards()
            self.game.phase = 'playing'
            
            # 顯示初始狀態
            self.show_initial_cards()
            
            # 檢查Blackjack
            self.game.check_blackjacks()
            
            # 玩家輪流行動
            self.players_turn()
            
            # 莊家補牌
            dealer_score = self.game.dealer_play()
            self.broadcast({
                'type': 'dealer_turn',
                'dealer_hand': self.game.dealer_hand,
                'dealer_score': dealer_score,
                'message': f'\n莊家補牌完成！'
            })
            
            # 判斷勝負
            self.game.determine_winners()
            
            # 顯示結果
            self.show_results()
            
            # 檢查是否有玩家破產
            bankrupt = [username for username in self.game.player_order 
                       if self.game.players[username]['chips'] <= 0]
            
            if bankrupt:
                # Determine final winner (player with most chips)
                results_list = []
                for username in self.game.player_order:
                    player = self.game.players[username]
                    results_list.append({
                        'username': username,
                        'chips': player['chips']
                    })
                
                results_list.sort(key=lambda x: x['chips'], reverse=True)
                winner = results_list[0]
                result_summary = f"玩家 {winner['username']} 獲勝！（${winner['chips']} 籌碼）"
                
                # Write game result to file for lobby server
                try:
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    with open(os.path.join(script_dir, 'game_result.txt'), 'w', encoding='utf-8') as f:
                        f.write(result_summary)
                    print(f"\n✅ 遊戲結果已寫入: {result_summary}")
                except Exception as e:
                    print(f"⚠️  無法寫入遊戲結果: {e}")
                
                self.broadcast({
                    'type': 'game_over',
                    'message': f'\n玩家 {", ".join(bankrupt)} 破產！遊戲結束！\n{result_summary}',
                    'results': results_list
                })
                break
            
            # 詢問是否繼續
            time.sleep(2)
            self.broadcast({
                'type': 'ask_continue',
                'message': '\n3秒後開始下一局...'
            })
            time.sleep(3)
    
    def betting_phase(self):
        """下注階段"""
        for username in self.game.player_order:
            sock = self.get_socket_by_username(username)
            player = self.game.players[username]
            
            self.send_message(sock, {
                'type': 'your_bet',
                'chips': player['chips'],
                'message': f'\n輪到你下注！你有 ${player["chips"]} 籌碼'
            })
            
            # 等待下注
            while True:
                data = self.recv_message(sock)
                if data and data['type'] == 'bet':
                    bet_amount = data['amount']
                    
                    if bet_amount <= 0:
                        self.send_message(sock, {
                            'type': 'error',
                            'message': '下注金額必須大於0'
                        })
                        continue
                    
                    if bet_amount > player['chips']:
                        self.send_message(sock, {
                            'type': 'error',
                            'message': f'籌碼不足！你只有 ${player["chips"]}'
                        })
                        continue
                    
                    # 下注成功
                    player['chips'] -= bet_amount
                    player['bet'] = bet_amount
                    player['can_double'] = (bet_amount <= player['chips'])
                    
                    self.send_message(sock, {
                        'type': 'bet_success',
                        'message': f'下注成功！你下注了 ${bet_amount}'
                    })
                    
                    self.broadcast_except(sock, {
                        'type': 'info',
                        'message': f'{username} 下注了 ${bet_amount}'
                    })
                    break
    
    def show_initial_cards(self):
        """顯示初始牌面"""
        # 莊家明牌
        visible_card = self.game.card_to_string(self.game.dealer_hand[1])
        visible_score = VALUES[self.game.dealer_hand[1]['rank']]
        
        msg = f'\n{"="*50}\n發牌完成！\n{"="*50}\n'
        msg += f'莊家: [{visible_card}, ?] (明牌點數: {visible_score})\n\n'
        
        for username in self.game.player_order:
            player = self.game.players[username]
            if player['bet'] > 0:
                hand_str = self.game.hand_to_string(player['hand'])
                score = self.game.calculate_hand(player['hand'])
                msg += f'{username}: [{hand_str}] (點數: {score}, 下注: ${player["bet"]})\n'
        
        self.broadcast({
            'type': 'initial_cards',
            'state': self.game.get_game_state(),
            'message': msg
        })
    
    def players_turn(self):
        """玩家回合"""
        for i, username in enumerate(self.game.player_order):
            player = self.game.players[username]
            
            if player['status'] != 'playing':
                continue
            
            self.game.current_player_index = i
            sock = self.get_socket_by_username(username)
            
            self.broadcast({
                'type': 'player_turn',
                'username': username,
                'message': f'\n>>> 輪到 {username} 行動'
            })
            
            # 玩家行動循環
            while player['status'] == 'playing':
                hand_str = self.game.hand_to_string(player['hand'])
                score = self.game.calculate_hand(player['hand'])
                
                actions = ['要牌(h)', '停牌(s)']
                if player['can_double']:
                    actions.append('加倍(d)')
                
                self.send_message(sock, {
                    'type': 'your_action',
                    'hand': hand_str,
                    'score': score,
                    'actions': actions,
                    'message': f'\n你的手牌: [{hand_str}] (點數: {score})\n請選擇動作: {" / ".join(actions)}'
                })
                
                # 等待動作
                data = self.recv_message(sock)
                if not data:
                    player['status'] = 'stand'
                    break
                
                if data['type'] == 'hit':
                    result, score = self.game.player_hit(username)
                    hand_str = self.game.hand_to_string(player['hand'])
                    
                    if result == 'bust':
                        msg = f'{username} 要牌後爆牌！[{hand_str}] (點數: {score})'
                        self.send_message(sock, {'type': 'bust', 'message': f'\n💥 {msg}'})
                        self.broadcast_except(sock, {'type': 'info', 'message': f'\n{msg}'})
                    elif result == 'stand':
                        msg = f'{username} 達到21點自動停牌！'
                        self.send_message(sock, {'type': 'auto_stand', 'message': f'\n✓ {msg}'})
                        self.broadcast_except(sock, {'type': 'info', 'message': f'\n{msg}'})
                    else:
                        self.send_message(sock, {
                            'type': 'hit_result',
                            'message': f'\n要牌：得到 {self.game.card_to_string(player["hand"][-1])}'
                        })
                
                elif data['type'] == 'stand':
                    self.game.player_stand(username)
                    msg = f'{username} 停牌！'
                    self.send_message(sock, {'type': 'stand_result', 'message': f'\n✓ {msg}'})
                    self.broadcast_except(sock, {'type': 'info', 'message': f'\n{msg}'})
                
                elif data['type'] == 'double':
                    success, score = self.game.player_double(username)
                    if success:
                        hand_str = self.game.hand_to_string(player['hand'])
                        msg = f'{username} 加倍！新下注: ${player["bet"]}'
                        
                        if player['status'] == 'bust':
                            msg += f' | 爆牌！[{hand_str}] (點數: {score})'
                            self.send_message(sock, {'type': 'bust', 'message': f'\n💥 {msg}'})
                        else:
                            msg += f' | 自動停牌 [{hand_str}] (點數: {score})'
                            self.send_message(sock, {'type': 'double_result', 'message': f'\n✓ {msg}'})
                        
                        self.broadcast_except(sock, {'type': 'info', 'message': f'\n{msg}'})
                    else:
                        self.send_message(sock, {'type': 'error', 'message': '\n無法加倍'})
    
    def show_results(self):
        """顯示結果"""
        dealer_hand_str = self.game.hand_to_string(self.game.dealer_hand)
        dealer_score = self.game.calculate_hand(self.game.dealer_hand)
        
        msg = f'\n{"="*50}\n第 {self.game.round} 局結果\n{"="*50}\n'
        msg += f'莊家: [{dealer_hand_str}] (點數: {dealer_score})\n\n'
        
        results = []
        for username in self.game.player_order:
            player = self.game.players[username]
            if player['bet'] == 0:
                continue
            
            hand_str = self.game.hand_to_string(player['hand'])
            score = self.game.calculate_hand(player['hand'])
            
            status_msg = {
                'blackjack': f'🎰 Blackjack! 贏得 ${int(player["bet"])}',
                'win': f'🎉 勝利！贏得 ${player["bet"]}',
                'lose': f'😞 失敗！輸掉 ${player["bet"]}',
                'bust': f'💥 爆牌！輸掉 ${player["bet"]}',
                'tie': f'🤝 平手！退回 ${player["bet"]}'
            }.get(player['status'], '')
            
            msg += f'{username}: [{hand_str}] (點數: {score}) - {status_msg}\n'
            msg += f'  剩餘籌碼: ${player["chips"]}\n\n'
            
            results.append({
                'username': username,
                'score': score,
                'status': player['status'],
                'chips': player['chips']
            })
        
        self.broadcast({
            'type': 'round_result',
            'results': results,
            'message': msg
        })
    
    def get_socket_by_username(self, username):
        """根據用戶名獲取socket"""
        for sock, uname in self.clients.items():
            if uname == username:
                return sock
        return None
    
    def broadcast(self, message):
        """廣播消息"""
        for sock in self.clients.keys():
            self.send_message(sock, message)
    
    def broadcast_except(self, except_sock, message):
        """廣播消息（排除指定socket）"""
        for sock in self.clients.keys():
            if sock != except_sock:
                self.send_message(sock, message)
    
    def send_message(self, sock, message):
        """發送消息"""
        try:
            data = json.dumps(message).encode('utf-8')
            sock.sendall(len(data).to_bytes(4, 'big') + data)
        except:
            pass
    
    def recv_message(self, sock):
        """接收消息"""
        try:
            length_bytes = sock.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, 'big')
            data = sock.recv(length)
            return json.loads(data.decode('utf-8'))
        except:
            return None


class BlackjackClient:
    def __init__(self, host='localhost', port=5001):
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.running = True
        
    def connect(self, username):
        """連接到服務器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.username = username
            
            # 發送加入請求
            self.send_message({
                'type': 'join',
                'username': username
            })
            
            # 等待歡迎消息
            msg = self.recv_message()
            if msg and msg['type'] == 'welcome':
                print(msg['message'])
                return True
        except Exception as e:
            print(f"連線失敗: {e}")
        return False
    
    def run(self):
        """運行客戶端"""
        print(f"\n{'='*60}")
        print(f"{'♠♥♦♣ BLACKJACK (21點) ♠♥♦♣':^60}")
        print(f"{'='*60}\n")
        
        username = input("請輸入你的名字: ").strip()
        if not username:
            username = f"Player{random.randint(1000, 9999)}"
        
        if not self.connect(username):
            return
        
        print(f"\n歡迎 {username}！正在等待遊戲開始...\n")
        
        while self.running:
            msg = self.recv_message()
            if not msg:
                break
            
            msg_type = msg['type']
            
            if msg_type in ['welcome', 'new_round', 'initial_cards', 'info', 
                           'player_turn', 'dealer_turn', 'round_result', 
                           'ask_continue', 'game_over']:
                if 'message' in msg:
                    print(msg['message'])
                
                if msg_type == 'game_over':
                    # 寫入遊戲結果
                    try:
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        with open(os.path.join(script_dir, 'game_result.txt'), 'w', encoding='utf-8') as f:
                            # 找出最終贏家（籌碼最多）
                            if 'results' in msg:
                                results = sorted(msg['results'], key=lambda x: x['chips'], reverse=True)
                                winner = results[0]
                                f.write(f"玩家 {winner['username']} 獲勝！（${winner['chips']} 籌碼）")
                            else:
                                f.write("遊戲結束")
                    except:
                        pass
                    
                    time.sleep(2)
                    self.running = False
            
            elif msg_type == 'your_bet':
                chips = msg['chips']
                print(msg['message'])
                
                while True:
                    try:
                        bet_input = input(f"請下注 (1-{chips}): ").strip()
                        bet_amount = int(bet_input)
                        
                        if bet_amount <= 0 or bet_amount > chips:
                            print(f"請輸入 1 到 {chips} 之間的數字")
                            continue
                        
                        self.send_message({
                            'type': 'bet',
                            'amount': bet_amount
                        })
                        break
                    except ValueError:
                        print("請輸入有效的數字")
                    except KeyboardInterrupt:
                        print("\n遊戲中斷")
                        self.running = False
                        return
            
            elif msg_type == 'bet_success':
                print(f"\n✓ {msg['message']}\n")
            
            elif msg_type == 'your_action':
                print(msg['message'])
                
                actions_map = {
                    'h': 'hit',
                    's': 'stand',
                    'd': 'double'
                }
                
                valid_actions = ['h', 's']
                if '加倍(d)' in msg['actions']:
                    valid_actions.append('d')
                
                while True:
                    try:
                        action = input("請選擇: ").strip().lower()
                        
                        if action not in valid_actions:
                            print(f"無效的選擇，請輸入: {', '.join(valid_actions)}")
                            continue
                        
                        self.send_message({
                            'type': actions_map[action]
                        })
                        break
                    except KeyboardInterrupt:
                        print("\n遊戲中斷")
                        self.running = False
                        return
            
            elif msg_type in ['hit_result', 'stand_result', 'double_result', 
                             'bust', 'auto_stand']:
                print(msg['message'])
            
            elif msg_type == 'error':
                print(f"\n⚠️ {msg['message']}")
        
        print("\n感謝遊玩！")
        self.socket.close()
    
    def send_message(self, message):
        """發送消息"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(len(data).to_bytes(4, 'big') + data)
        except:
            pass
    
    def recv_message(self):
        """接收消息"""
        try:
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, 'big')
            data = self.socket.recv(length)
            return json.loads(data.decode('utf-8'))
        except:
            return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Server: python game.py server [--port PORT]")
        print("  Client: python game.py client [--host HOST] [--port PORT]")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "server":
        port = 5001
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        
        server = BlackjackServer(port=port)
        server.start()
    
    elif mode == "client":
        host = 'localhost'
        port = 5001
        
        for i, arg in enumerate(sys.argv):
            if arg == "--host" and i + 1 < len(sys.argv):
                host = sys.argv[i + 1]
            elif arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        
        client = BlackjackClient(host, port)
        client.run()
    
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
