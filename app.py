# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify, Response, g, session, \
    send_file
from wtforms import validators, PasswordField
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
import base64
import sqlite3
import datetime
from gevent import pywsgi
import os, cv2, time
from datetime import timedelta
import numpy as np

from SiamFC.tracker import TrackerSiamFC

last_frame = None
video_alive = False
ALLOWED_EXTENSIONS = {'mp4', 'ts', 'avi'}  # 设置允许的文件格式
app = Flask(__name__)
app.secret_key = "shawroot"
app.config['FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'user')

# 设置session过期时间为4个小时
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=4)

# 将os模块添加到Jinja2模板的全局上下文
@app.context_processor
def inject_os():
    return dict(os=os)

# 创建数据库
def init():
    # 连接SQLite数据库
    conn = sqlite3.connect('mydatabase.db')
    c = conn.cursor()

    # 创建用户表格
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  password TEXT NOT NULL)''')
    conn.commit()
    c.close()


import threading

# 创建线程本地存储对象
local = threading.local()


# 在函数内部获取当前线程的 SQLite 对象
def get_conn():
    if not hasattr(local, 'conn'):
        local.conn = sqlite3.connect('mydatabase.db')
    return local.conn


# 关闭连接
def close_conn():
    conn = getattr(local, 'conn', None)
    if conn:
        conn.close()
        local.conn = None


# 判断文件类型
def allowed_file(filename):
    print(filename.rsplit('.', 1)[1])
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


# 修改文件名字
def rename(filename):
    filename = filename.split('.')
    print(filename)
    return filename[0] + '_'+str(np.random.randint(213, 1000)) + '.'+ filename[1]




# 设置文件过期时间
app.send_file_max_age_default = timedelta(seconds=1)


# 处理视频
def resize_and_save(filepath):


    # 读取视频
    cap = cv2.VideoCapture(filepath)
    # 设置新的尺寸
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if max(width, height) <= 500:
        return 'yes'

    os.remove(filepath)
    print(width, height)

    new_width = 480
    new_height = int((height/width) * new_width)

    print(new_width, new_height)
    # 获取视频的原始 FPS 和编码格式
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    # 创建一个新的视频文件，用于保存调整尺寸后的视频
    out = cv2.VideoWriter(
        # os.path.join(app.config['FOLDER'], session['username'], 'ss.avi'),
        filepath,
        fourcc,
        fps,
        (new_width, new_height)
    )

    # 处理视频的每一帧，调整尺寸并写入新文件
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        resized_frame = cv2.resize(frame, (new_width, new_height))
        out.write(resized_frame)

    # 释放资源
    cap.release()
    out.release()
    cv2.destroyAllWindows()

# 上传函数
@app.route('/upload', methods=['POST'])
def upload():
    global filename
    if 'username' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        f = request.files['file']
        size = int(request.form.get('size', 300))

        if not (f and allowed_file(f.filename)):
            return jsonify({"st": 1001, "msg": "请检查上传文件的类型，仅限于mp4、ts, avi"}), 200

        upload_path = os.path.join(app.config['FOLDER'], session['username'])
        filename = f.filename
        if os.path.exists(os.path.join(upload_path, filename)):
            filename = rename(filename)
            print(filename)

        upload_path = os.path.join(upload_path, filename)

        print(upload_path)
        f.save(upload_path)

        resize_and_save(upload_path)


        return jsonify({'st':200, 'msg':'上传成功'}), 200

# 删除视频
@app.route('/delete_file', methods=['DELETE'])
def delete_file():
    filename = request.args.get('name')
    if not filename:
        return jsonify({'message': '文件名参数缺失'}), 400
    try:
        os.remove(os.path.join(app.config['FOLDER'], session['username'], filename))
        return jsonify({'message': '删除成功'})
    except OSError:
        return jsonify({'message': '文件不存在或无法删除'}), 400

# 完整视频流响应
@app.route('/video_feed/<path:filepath>')
def video_feed(filepath):
    if 'username' not in session:
        return redirect(url_for('index'))

    # 完整的播放视频
    def get_frame(upload_path):
        camera = cv2.VideoCapture(upload_path)
        i = 1
        while True:
            retval, im = camera.read()
            if retval:
                imgencode = cv2.imencode('.jpg', im)[1]
                stringData = imgencode.tostring()
                yield (b'--frame\r\n'
                       b'Content-Type: text/plain\r\n\r\n' + stringData + b'\r\n')
                i += 1
            else:
                camera.release()

    filepath = os.path.join('/', filepath)
    return Response(get_frame(filepath), mimetype='multipart/x-mixed-replace; boundary=frame')


# 返回第一帧图像
@app.route('/adress_video/<path:filepath>', methods=['POST', 'GET'])
def adress_video(filepath):
    if 'username' not in session:
        return redirect(url_for('index'))

    print(filepath)
    # 返回第一帧
    filepath = os.path.join('/', filepath)
    print(filepath)
    def adress_frame(path, model_name):
        cap = cv2.VideoCapture(path)
        success, frame = cap.read()
        imgencode = cv2.imencode('.jpg', frame)[1]
        stringData = imgencode.tostring()
        yield (b'--frame\r\n'
               b'Content-Type: text/plain\r\n\r\n' + stringData + b'\r\n')
        cap.release()

    return Response(adress_frame(filepath, 'SiamFC'),
                    mimetype='multipart/x-mixed-replace; boundary=frame')



# 获得box
@app.route('/test_tracking', methods=['POST', 'GET'])
def test_tracking():
    if 'username' not in session:
        return redirect(url_for('index'))

    session['box'] = request.json
    print(session.get('box'))
    return 'yes'
    # return render_template('play.html')


# 返回response
@app.route('/play/<path:filepath>')
def video(filepath):
    if 'username' not in session:
        return redirect(url_for('index'))

    # 追踪模型
    def get_json(path, box):
        # print(box)
        model = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'SiamFC', "model.pth")
        print(model)
        tracker = TrackerSiamFC(model)
        print(path)
        cap = cv2.VideoCapture(path)
        success, frame = cap.read()

        tracker.init(frame, box)

        i = 1
        while 1:
            success, frame = cap.read()
            if not success:
                cap.release()
                break

            pred = tracker.update(frame)

            cv2.rectangle(frame, (int(pred[0]), int(pred[1])), (int(pred[0] + pred[2]), int(pred[1] + pred[3])),
                          (0, 255, 255),
                          3)
            imgencode = cv2.imencode('.jpg', frame)[1]
            stringData = imgencode.tostring()
            yield (b'--frame\r\n'
                   b'Content-Type: text/plain\r\n\r\n' + stringData + b'\r\n')
            i += 1
        cap.release()

    filepath = os.path.join('/', filepath)
    box = session.get('box')
    return Response(
        get_json(filepath,
                 [box['x'], box['y'], box['x1'] - box['x'], box['y1'] - box['y']]),
        mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/play_video/<path:filepath>')
def play_video(filepath):
    if 'username' not in session:
        return redirect(url_for('index'))

    filepath = os.path.join('/', filepath)
    return render_template('play.html', filepath=filepath)


@app.route('/pre_track')
def pre():
    if 'username' not in session:
        return redirect(url_for('index'))

    return render_template('index.html', file_path=os.path.join(app.config['FOLDER'], session['username']))


# 注册路由
@app.route('/', methods=['GET', 'POST'])
def index():
    # 如果用户已经登录，则重定向到dashboard路由
    if 'username' in session:
        return redirect(url_for('dashboard'))

    conn = get_conn()
    c = conn.cursor()
    # 处理用户提交的登录或注册请求
    if request.method == 'POST':
        if request.form['submit'] == '登录':
            username = request.form['username']
            password = request.form['password']
            print(username, password)
            c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
            user = c.fetchone()
            print(user)
            if user:
                session['username'] = user[1]
                return redirect(url_for('dashboard'))
            else:
                error = '用户名或密码错误'
                return render_template('login.html', error=error)

        elif request.form['submit'] == '注册':
            username = request.form['username']
            password = request.form['password']
            c.execute('SELECT * FROM users WHERE username=?', (username,))
            user = c.fetchone()
            if user:
                error = '该用户名已经被注册'
                return render_template('login.html', error=error)
            else:
                c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
                conn.commit()
                session['username'] = username
                folder_path = os.path.join(app.config['FOLDER'], session['username'])
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                return redirect(url_for('dashboard'))
    close_conn()
    # 显示登录或注册页面
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    # 如果用户没有登录，则重定向到登录页面
    if 'username' not in session:
        return redirect(url_for('index'))
    # 显示dashboard页面
    return render_template('my.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route("/get_file_list")
def get_file_list():
    if 'username' not in session:
        return redirect(url_for('index'))
    folder_path = os.path.join(app.config['FOLDER'], session['username'])
    file_list = os.listdir(folder_path)
    return "\n".join(file_list)

@app.route('/select', methods=['POST'])
def select():
    filename = request.form['filename']
    filepath = os.path.join(app.config['FOLDER'], session['username'], filename);
    cap = cv2.VideoCapture(filepath)
    # 设置新的尺寸
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return render_template('tracking.html', filepath=filepath, width=width, height=height)



if __name__ == '__main__':
    # server = pywsgi.WSGIServer(('0.0.0.0', 5000), app)
    # server.serve_forever()
    app.run(host='0.0.0.0', port=5000, debug=True)
