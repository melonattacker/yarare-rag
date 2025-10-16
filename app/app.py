# app.py
import os
import uuid
import logging
import sys
import re
from ipaddress import ip_address, ip_network
from flask import Flask, request, redirect, render_template, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

# ルーティング以外の処理は helpers.py に分離
from helpers import (
    query_db, execute_db, render_markdown,
    rag, answer_with_context,
    get_related_memos, _get_tags_for_memo,
    search_memos_by_tag,
    generate_tags, attach_tags,
    save_memo
)

# Flask アプリ初期化
app = Flask(__name__)
app.secret_key = os.getenv("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# レートリミットの設定
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="redis://redis:6379",
)
TRUSTED_NETWORKS = [
    ip_network("172.16.0.0/12")  # docker-compose
]
@limiter.request_filter
def ip_whitelist():
    # docker-compose のネットワーク内からのアクセスはレートリミットを適用しない
    ip = get_remote_address()
    try:
        ip_obj = ip_address(ip)
    except ValueError:
        return False # 無効なIPアドレスはホワイトリストにしない
    return any(ip_obj in net for net in TRUSTED_NETWORKS)

# ログイン or ユーザーページへリダイレクト
@app.route('/')
def index():
    """セッションの有無でログインページまたはユーザページに振り分ける。"""
    if 'user_id' in session:
        return redirect(f"/users/{session['user_id']}")
    return redirect(url_for('login'))

# ユーザー登録
@app.route('/register', methods=['GET', 'POST'])
def register():
    """新規ユーザー登録フォームの表示と登録処理を行う。"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # ユーザー名の重複確認
        existing = query_db("SELECT 1 FROM users WHERE username=%s", (username,), fetchone=True)
        if existing:
            return 'このユーザー名は既に使われています。', 409

        # ユーザー作成とログイン状態の確立
        user_id = str(uuid.uuid4())
        execute_db("INSERT INTO users (id, username, password) VALUES (%s, %s, %s)",
                   (user_id, username, password))
        session['user_id'] = user_id
        return redirect(f"/users/{user_id}")

    return render_template('register.html')

# ログイン
@app.route('/login', methods=['GET', 'POST'])
def login():
    """ログインフォームの表示と認証処理を行う。"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = query_db("SELECT * FROM users WHERE username=%s AND password=%s",
                        (username, password), fetchone=True)
        if user:
            session['user_id'] = user['id']
            return redirect(f"/users/{user['id']}")
        return 'ユーザー名またはパスワードが間違っています。', 403

    return render_template('login.html')

# ログアウト
@app.route('/logout')
def logout():
    """ログアウトしてログインページに戻す。"""
    session.clear()
    return redirect(url_for('login'))

# ユーザーページ
@app.route('/users/<uid>')
def user_page(uid):
    """対象ユーザーのメモ一覧を表示する。本人は非公開メモの情報も見られる。"""
    current = session.get('user_id')

    user = query_db("SELECT username FROM users WHERE id=%s", (uid,), fetchone=True)
    if not user:
        return "User not found. <a href='/register'>Register</a> or <a href='/login'>Login</a>", 404

    if current == uid:
        sql = """
            SELECT id, body, visibility FROM memos WHERE user_id=%s AND visibility IN ('public','private')
            UNION 
            SELECT id, '🔒秘密メモ' AS body, 'secret' AS visibility FROM memos WHERE user_id=%s AND visibility='secret'
        """
        memos = query_db(sql, (uid, uid))
    else:
        memos = query_db("SELECT id, body, visibility FROM memos WHERE user_id=%s AND visibility='public'", (uid,))
    
    return render_template('index.html', memos=memos, username=user["username"], user_id=uid)

# メモ詳細
@app.route('/memo/<mid>', methods=['GET', 'POST'])
def memo_detail(mid):
    """メモの詳細を表示する。秘密メモはパスワードを確認する。"""
    uid = session.get('user_id')
    memo = query_db(
        'SELECT id, user_id, body, visibility, password, created_at '
        'FROM memos WHERE id=%s',
        (mid,), fetchone=True
    )
    if not memo:
        return 'Not found', 404
    if memo['user_id'] != uid:
        return 'Forbidden', 403

    # 秘密メモのアクセス処理
    if memo['visibility'] == 'secret':
        if request.method == 'POST' and request.form.get('password') == memo.get('password'):
            related = get_related_memos(mid, limit=1)
            return render_template(
                'detail.html',
                memo=memo, authorized=True,
                related=related, tags=_get_tags_for_memo(mid),
                memo_html=render_markdown(memo['body'])
            )
        if request.method == 'GET':
            return render_template(
                'detail.html',
                memo=memo, authorized=False,
                related=[], tags=_get_tags_for_memo(mid)
            )
        return ('Wrong password', 403)

    # 公開/非公開メモの表示
    related = get_related_memos(mid, limit=1)
    return render_template(
        'detail.html',
        memo=memo, authorized=True,
        related=related, tags=_get_tags_for_memo(mid),
        memo_html=render_markdown(memo['body'])
    )

# メモ作成
@app.route('/memo/create', methods=['GET', 'POST'])
def memo_create():
    """メモの作成フォーム表示と作成処理を行う。"""
    uid = session.get('user_id')
    if not uid:
        return redirect('/')

    if request.method == 'POST':
        # ユーザーの既存メモ数を確認
        memo_count = query_db("SELECT COUNT(*) AS count FROM memos WHERE user_id=%s",
                              (uid,), fetchone=True)['count']
        if memo_count >= 5:
            return "メモは5つまでしか作成できません。", 403

        # 入力値の取得と検証
        body = request.form.get('body', '')
        if len(body) > 300:
            return "メモは300字以下で入力してください。", 400

        visibility = request.form.get('visibility', 'public')
        password = request.form.get('password', '') if visibility == 'secret' else None
        generate_tags_flag = request.form.get('enable_tags') == 'on'

        # メモの登録
        mid = str(uuid.uuid4())

        # メモの保存
        save_memo(mid, uid, body, visibility, password)

        # タグ生成と紐付け
        if generate_tags_flag:
            tags = generate_tags(body)
            attach_tags(mid, tags)

        return redirect(f'/memo/{mid}')

    return render_template('create.html')

@app.route('/memo/<mid>/delete', methods=['POST'])
def memo_delete(mid):
    """メモを削除する。本人のみ実行できる。"""
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))

    memo = query_db('SELECT user_id FROM memos WHERE id=%s', (mid,), fetchone=True)
    if not memo:
        return 'Not found', 404
    if memo['user_id'] != uid:
        return 'Forbidden', 403

    execute_db('DELETE FROM memos WHERE id=%s', (mid,))
    return redirect(f"/users/{uid}")

# タグ検索
@app.route('/tag/search')
def search_by_tag():
    """タグ名でメモを検索し、結果を表示する。"""
    uid = session.get('user_id')
    if not uid:
        return redirect(url_for('login'))

    tag_name = request.args.get('name', '').strip()
    if not tag_name:
        return render_template('tag_search.html', tag_name='', memos=[])

    memos = search_memos_by_tag(tag_name)
    return render_template('tag_search.html', tag_name=tag_name, memos=memos)

# RAG 検索フォーム
@app.route('/memo/search', methods=['GET'])
def search_form():
    """RAG 検索フォームを表示する。"""
    logging.info(f"RAG search form accessed from {request.remote_addr}")
    logging.info(f"{get_remote_address()}")
    uid = session.get('user_id')
    if not uid:
        return redirect('/')
    q = request.args.get('q', '')
    other_uid = request.args.get('user_id', '')
    return render_template('search.html', answer=None, query=q, other_user_id=other_uid)

# RAG 検索実行
@app.route('/memo/search', methods=['POST'])
@limiter.limit("5 per minute")
def search():
    """RAG でメモを検索し、回答を生成して表示する。"""
    uid = session.get('user_id')
    if not uid:
        return redirect('/')

    query = request.form.get('query') or request.args.get('q', '')
    other_user_id = request.form.get('user_id') or request.args.get('user_id', '') or None

    memos = rag(query, uid, other_user_id=other_user_id)
    logging.info(f"RAG memos: {memos}")

    if not (memos and isinstance(memos, list)):
        answer = "関連するメモが見つかりませんでした。"
    else:
        if 'user_id' in memos[0]:
            # 投稿者情報を返すケース
            answer = f"User ID: {memos[0]['user_id']}"
        else:
            # コンテキストを元に回答を作成
            answer = answer_with_context(query, memos)
            logging.info(f"RAG answer: {answer}")

            # flag の形式にマッチする場合は伏字にする
            answer = re.sub(r'flag\{[^\}]+\}', 'flag{****}', answer, flags=re.IGNORECASE)

    # Markdown 表示用に HTML へ変換
    answer_html = render_markdown(answer)
    return render_template('search.html', answer_html=answer_html, query=query, other_user_id=other_user_id or '')

# ログ出力の設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

__all__ = ["app"]