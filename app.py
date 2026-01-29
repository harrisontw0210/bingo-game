import socket
import qrcode
import io
import base64
import random
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

players = {}
drawn_numbers = []
target_player_count = 0

# --- 設定：幾條線獲勝 ---
WINNING_LINES = 3 

@app.route('/')
def index():
    return render_template('host.html')

@app.route('/play')
def play():
    return render_template('player.html')

@app.route('/get_qr')
def get_qr():
    # 自動抓取正確網址 (Render 或 Local)
    base_url = request.url_root.rstrip('/')
    url = f"{base_url}/play"
    
    img = qrcode.make(url)
    data = io.BytesIO()
    img.save(data, "PNG")
    encoded_img = base64.b64encode(data.getvalue()).decode('utf-8')
    
    return {"qr_image": f"data:image/png;base64,{encoded_img}", "url": url}

# --- SocketIO 事件 ---

@socketio.on('set_target')
def handle_set_target(count):
    global target_player_count
    target_player_count = int(count)
    # 更新前端資訊
    socketio.emit('update_dashboard', {'players': players, 'target': target_player_count, 'win_limit': WINNING_LINES})

@socketio.on('join_game')
def handle_join(data):
    name = data.get('name')
    players[request.sid] = {
        'name': name,
        'card': [],
        'lines': 0,
        'marked': [],
        'is_ready': False,
        'has_won': False
    }
    socketio.emit('update_dashboard', {'players': players, 'target': target_player_count, 'win_limit': WINNING_LINES})
    # 若中途加入，補傳已開出的號碼
    emit('sync_drawn_numbers', drawn_numbers)

@socketio.on('submit_card')
def handle_submit(card_data):
    if request.sid in players:
        players[request.sid]['card'] = card_data
        players[request.sid]['is_ready'] = True
        socketio.emit('update_dashboard', {'players': players, 'target': target_player_count, 'win_limit': WINNING_LINES})

@socketio.on('report_status')
def handle_status(data):
    if request.sid in players:
        current_lines = data['lines']
        players[request.sid]['lines'] = current_lines
        players[request.sid]['marked'] = data['marked']
        
        # 檢查是否達到獲勝標準 (且之前沒贏過，避免重複廣播)
        if current_lines >= WINNING_LINES and not players[request.sid]['has_won']:
            players[request.sid]['has_won'] = True
            socketio.emit('game_winner', players[request.sid]['name'])
            
        socketio.emit('update_dashboard', {'players': players, 'target': target_player_count, 'win_limit': WINNING_LINES})

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in players:
        del players[request.sid]
        socketio.emit('update_dashboard', {'players': players, 'target': target_player_count, 'win_limit': WINNING_LINES})

# --- 主控台指令 ---

@socketio.on('host_draw_number')
def host_draw():
    # 1-25 抽完就停
    if len(drawn_numbers) >= 25:
        return

    while True:
        num = random.randint(1, 25)
        if num not in drawn_numbers:
            drawn_numbers.append(num)
            socketio.emit('number_drawn', num)
            break

@socketio.on('host_reset')
def host_reset():
    global drawn_numbers
    drawn_numbers = []
    # 重置所有狀態但保留玩家連線
    for pid in players:
        players[pid]['marked'] = []
        players[pid]['lines'] = 0
        players[pid]['is_ready'] = False
        players[pid]['card'] = []
        players[pid]['has_won'] = False
    
    socketio.emit('reset_game')
    socketio.emit('update_dashboard', {'players': players, 'target': target_player_count, 'win_limit': WINNING_LINES})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)