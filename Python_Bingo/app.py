import socket
import qrcode
import io
import base64
import random
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# 允許跨域，確保雲端連線順暢
socketio = SocketIO(app, cors_allowed_origins="*")

# 儲存遊戲狀態
players = {}
drawn_numbers = []

# --- 路由區 ---

@app.route('/')
def index():
    return render_template('host.html')

@app.route('/play')
def play():
    return render_template('player.html')

@app.route('/get_qr')
def get_qr():
    """
    修改重點：自動抓取目前的網址 (request.url_root)
    這樣無論是在 Localhost 還是 Render 雲端，QR Code 都會是對的
    """
    # 移除網址末端的斜線，並加上 /play
    base_url = request.url_root.rstrip('/')
    url = f"{base_url}/play"
    
    # 產生 QR Code 圖片
    img = qrcode.make(url)
    data = io.BytesIO()
    img.save(data, "PNG")
    encoded_img = base64.b64encode(data.getvalue()).decode('utf-8')
    
    return {"qr_image": f"data:image/png;base64,{encoded_img}", "url": url}

# --- SocketIO 事件區 ---

@socketio.on('join_game')
def handle_join(data):
    name = data.get('name')
    players[request.sid] = {
        'name': name,
        'card': [],
        'lines': 0,
        'marked': []
    }
    socketio.emit('update_dashboard', players)
    # 如果中途加入，同步目前已開出的號碼
    emit('sync_drawn_numbers', drawn_numbers)

@socketio.on('submit_card')
def handle_submit(card_data):
    if request.sid in players:
        players[request.sid]['card'] = card_data
        socketio.emit('update_dashboard', players)

@socketio.on('report_status')
def handle_status(data):
    if request.sid in players:
        players[request.sid]['lines'] = data['lines']
        players[request.sid]['marked'] = data['marked']
        socketio.emit('update_dashboard', players)
        
        if data['lines'] >= 5:
            socketio.emit('game_winner', players[request.sid]['name'])

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in players:
        del players[request.sid]
        socketio.emit('update_dashboard', players)

# --- 主控台指令 (1-25版) ---

@socketio.on('host_draw_number')
def host_draw():
    # 範圍只有 25，抽完就停
    if len(drawn_numbers) >= 25:
        return

    while True:
        num = random.randint(1, 25) # 設定範圍 1-25
        if num not in drawn_numbers:
            drawn_numbers.append(num)
            socketio.emit('number_drawn', num)
            break

@socketio.on('host_reset')
def host_reset():
    global drawn_numbers
    drawn_numbers = []
    # 重置玩家狀態
    for pid in players:
        players[pid]['marked'] = []
        players[pid]['lines'] = 0
    socketio.emit('reset_game')
    socketio.emit('update_dashboard', players)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)