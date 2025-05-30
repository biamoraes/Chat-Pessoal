from flask import Flask, redirect, render_template, request, url_for, session
from flask_socketio import SocketIO, emit
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = "chave_secreta"
socketio = SocketIO(app)

app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nome_usuario = request.form.get('nome_usuario')
        senha = request.form.get('senha')
        telefone = request.form.get('telefone')
        imagem = request.files.get('imagem')
        imagem_filename = secure_filename(imagem.filename) if imagem and imagem.filename else None
        if imagem_filename:
            imagem_path = os.path.join(app.config['UPLOAD_FOLDER'], imagem_filename)
            imagem.save(imagem_path)
        with sqlite3.connect('models/chatbanco.db') as conexao:
            conexao.execute(
                'INSERT INTO tb_login (nome_usuario, senha, telefone, imagem) VALUES (?, ?, ?, ?)',
                (nome_usuario, senha, telefone, imagem_filename)
            )
        return redirect('/')
    return render_template('cadastro.html')

@app.route('/login', methods=['POST'])
def login():
    usuario = request.form.get('usuario')
    senha = request.form.get('senha')
    with sqlite3.connect('models/chatbanco.db') as conexao:
        cursor = conexao.execute("SELECT * FROM tb_login WHERE nome_usuario=? AND senha=?", (usuario, senha))
        usuario_dados = cursor.fetchone()
    if usuario_dados:
        # Modificado para desempacotar corretamente os dados do usuário
        id_usuario, senha_db, nome_usuario, imagem, telefone = usuario_dados
        session['id_usuario'] = id_usuario
        session['usuario'] = nome_usuario
        session['imagem'] = imagem
        return redirect('/mensagem')
    return redirect('/')

def get_mensagens():
    with sqlite3.connect('models/chatbanco.db') as conexao:
        cursor = conexao.execute(
            """
            SELECT tb_chat.mensagem, tb_login.nome_usuario, tb_chat.data_hora, tb_login.imagem
            FROM tb_chat
            JOIN tb_login ON tb_chat.id_usuario = tb_login.id
            ORDER BY tb_chat.id ASC
            """
        )
        mensagens = [
            (msg or "", user or "Usuário Desconhecido", datetime.strptime(data, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M:%S') if data else "Sem data", img or "")
            for msg, user, data, img in cursor.fetchall()
        ]
    return mensagens

@app.route('/mensagem', methods=['GET', 'POST'])
def mensagem():
    if 'usuario' not in session:
        return redirect('/')
    if 'mensagem_enviada' in session and session['mensagem_enviada']:
        del session['mensagem_enviada']
    if request.method == 'POST':
        mensagem_texto = request.form.get('msgg')
        if mensagem_texto:
            data_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect('models/chatbanco.db') as conexao:
                conexao.execute(
                    "INSERT INTO tb_chat(id_usuario, mensagem, data_hora) VALUES (?, ?, ?)",
                    (session['id_usuario'], mensagem_texto, data_hora)
                )
            socketio.emit('nova_mensagem', {
                'mensagem': mensagem_texto,
                'usuario': session.get('usuario', 'Usuário Desconhecido'),
                'data_hora': data_hora,
                'imagem': session.get('imagem', '')
            })
            session['mensagem_enviada'] = True
            return redirect(url_for('mensagem'))
    return render_template('chat.html', usuario=session['usuario'], imagem=session.get('imagem', ''), mensagens=get_mensagens())

@socketio.on('nova_mensagem')
def handle_nova_mensagem(data):
    # Inserido handler para o evento via Socket.IO
    mensagem_texto = data.get('mensagem')
    usuario = data.get('usuario')
    data_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    id_usuario = session.get('id_usuario')
    if id_usuario and mensagem_texto:
        with sqlite3.connect('models/chatbanco.db') as conexao:
            conexao.execute(
                "INSERT INTO tb_chat(id_usuario, mensagem, data_hora) VALUES (?, ?, ?)",
                (id_usuario, mensagem_texto, data_hora)
            )
    emit('nova_mensagem', {
        'mensagem': mensagem_texto,
        'usuario': usuario,
        'data_hora': data_hora,
        'imagem': session.get('imagem', '')
    }, broadcast=True)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == '__main__':
    socketio.run(app, host="127.0.0.1", port=80, debug=True)

