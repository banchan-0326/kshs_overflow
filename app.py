import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename # 이미지 업로드용
# from models import User, UserProfile, Post, Notification # models.py를 사용하지 않으므로 주석 처리 또는 삭제
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectMultipleField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed # 이미지 업로드용

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = "ganggwak_overflow.db"
SUBJECT_CHOICES = [
    ('수학', '수학'), ('물리', '물리'), ('물리실험', '물리실험'),
    ('화학', '화학'), ('화학실험', '화학실험'), ('지구과학', '지구과학'),
    ('지구과학실험', '지구과학실험'), ('생명과학', '생명과학'), ('생명과학 실험', '생명과학 실험'),
    ('정보', '정보'), ('인공지능', '인공지능')
]

# --- App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key_here' # 나중에 더 강력한 키로 변경하세요
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, DB_NAME)}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# --- Database Setup ---
db = SQLAlchemy(app)

# --- Login Manager Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # 로그인 페이지 라우트 이름
login_manager.login_message = "로그인이 필요한 페이지입니다."
login_manager.login_message_category = "info"


# --- Models ---
# (models.py로 분리 예정, 초기에는 여기에 작성)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False) # 학번+이름
    password_hash = db.Column(db.String(200), nullable=False)
    profile = db.relationship('UserProfile', backref='user', uselist=False, lazy=True)
    posts = db.relationship('Post', backref='author', lazy=True)
    notifications_received = db.relationship('Notification', foreign_keys='Notification.recipient_id', backref='recipient', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    academic_club = db.Column(db.String(100))
    creative_club = db.Column(db.String(100))
    autonomous_club1 = db.Column(db.String(100), nullable=True)
    autonomous_club2 = db.Column(db.String(100), nullable=True)
    autonomous_club3 = db.Column(db.String(100), nullable=True)
    interests = db.Column(db.String(500), default='') # 쉼표로 구분된 문자열
    strengths = db.Column(db.String(500), default='') # 쉼표로 구분된 문자열

    def get_interests_list(self):
        return [interest.strip() for interest in self.interests.split(',') if interest.strip()] if self.interests else []

    def get_strengths_list(self):
        return [strength.strip() for strength in self.strengths.split(',') if strength.strip()] if self.strengths else []


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(200), nullable=True) # 첨부 이미지 파일명
    subject = db.Column(db.String(50), nullable=False) # 게시글 분야
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Post {self.title}>"

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    author = db.relationship('User', backref='comments')

    def __repr__(self):
        return f"<Comment '{self.content[:30]}...'>"

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True) # 어떤 게시글 관련 알림인지
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Notification {self.message[:30]}>'


# --- Forms ---
# (forms.py로 분리 예정, 초기에는 여기에 작성)
class RegistrationForm(FlaskForm):
    username = StringField('학번+이름', validators=[DataRequired(), Length(min=4, max=100)])
    password = PasswordField('비밀번호', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('비밀번호 확인', validators=[DataRequired(), EqualTo('password', message='비밀번호가 일치하지 않습니다.')])
    submit = SubmitField('회원가입')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('이미 사용 중인 학번+이름입니다. 다른 이름을 사용해주세요.')

class LoginForm(FlaskForm):
    username = StringField('학번+이름', validators=[DataRequired()])
    password = PasswordField('비밀번호', validators=[DataRequired()])
    submit = SubmitField('로그인')

class ProfileForm(FlaskForm):
    academic_club = StringField('학술 동아리', validators=[Length(max=100)])
    creative_club = StringField('창체 동아리', validators=[Length(max=100)])
    autonomous_club1 = StringField('자율 동아리 1', validators=[Length(max=100)], render_kw={"placeholder": "선택 사항"})
    autonomous_club2 = StringField('자율 동아리 2', validators=[Length(max=100)], render_kw={"placeholder": "선택 사항"})
    autonomous_club3 = StringField('자율 동아리 3', validators=[Length(max=100)], render_kw={"placeholder": "선택 사항"})
    interests = SelectMultipleField('관심 분야 (다중 선택 가능)', choices=SUBJECT_CHOICES, coerce=str)
    strengths = SelectMultipleField('자신있는 분야 (다중 선택 가능)', choices=SUBJECT_CHOICES, coerce=str)
    submit = SubmitField('프로필 저장')

class PostForm(FlaskForm):
    title = StringField('제목', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('내용', validators=[DataRequired()])
    image = FileField('이미지 첨부 (선택 사항)', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'], '이미지 파일만 업로드 가능합니다!')])
    subject = SelectField('게시글 분야', choices=SUBJECT_CHOICES, validators=[DataRequired()])
    submit = SubmitField('글 작성')

class CommentForm(FlaskForm):
    content = TextAreaField('댓글', validators=[DataRequired(), Length(min=1, max=500)])
    submit = SubmitField('댓글 작성')

# --- Routes ---
@app.route('/')
@app.route('/home')
def home():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('index.html', posts=posts, title="커뮤니티 홈")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        # 기본 프로필 생성
        profile = UserProfile(user_id=user.id)
        db.session.add(profile)
        db.session.commit()
        flash('회원가입이 완료되었습니다! 이제 로그인할 수 있습니다.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='회원가입', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('로그인되었습니다!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('로그인에 실패했습니다. 학번+이름 또는 비밀번호를 확인해주세요.', 'danger')
    return render_template('login.html', title='로그인', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    profile_data = current_user.profile
    if not profile_data: # 혹시 프로필이 없는 경우 (회원가입 시 생성하므로 거의 발생 안함)
        profile_data = UserProfile(user_id=current_user.id)
        db.session.add(profile_data)
        db.session.commit()

    form = ProfileForm(obj=profile_data) # 기존 데이터로 폼 채우기
    # 현재 저장된 관심/자신있는 분야를 폼에 설정
    if request.method == 'GET':
        form.interests.data = profile_data.get_interests_list()
        form.strengths.data = profile_data.get_strengths_list()

    if form.validate_on_submit():
        profile_data.academic_club = form.academic_club.data
        profile_data.creative_club = form.creative_club.data
        profile_data.autonomous_club1 = form.autonomous_club1.data
        profile_data.autonomous_club2 = form.autonomous_club2.data
        profile_data.autonomous_club3 = form.autonomous_club3.data
        profile_data.interests = ','.join(form.interests.data)
        profile_data.strengths = ','.join(form.strengths.data)
        db.session.commit()
        flash('프로필이 성공적으로 업데이트되었습니다.', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', title='개인 정보', form=form)


@app.route('/create_post', methods=['GET', 'POST'])
@login_required
def create_post():
    form = PostForm()
    if form.validate_on_submit():
        new_post = Post(
            title=form.title.data,
            content=form.content.data,
            subject=form.subject.data,
            user_id=current_user.id
        )

        if form.image.data:
            image_file = form.image.data
            filename = secure_filename(image_file.filename)
            # 파일명을 고유하게 만들기 위해 (예: timestamp 또는 uuid 추가)
            # 여기서는 간단히 원래 파일명 사용. 실제 서비스에서는 중복 방지 처리 필요
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                image_file.save(image_path)
                new_post.image_filename = filename
            except Exception as e:
                flash(f'이미지 저장 중 오류 발생: {e}', 'danger')

        db.session.add(new_post)
        db.session.commit()

        # 알림 생성 로직
        # 해당 분야에 관심/강점이 있는 사용자들에게 알림
        users_to_notify = User.query.join(UserProfile).filter(
            (UserProfile.interests.contains(form.subject.data)) |
            (UserProfile.strengths.contains(form.subject.data)),
            User.id != current_user.id # 자기 자신에게는 알림 X
        ).all()

        for user in users_to_notify:
            notification_message = f"새로운 '{form.subject.data}' 관련 글이 등록되었습니다: '{new_post.title}'"
            notification = Notification(recipient_id=user.id, post_id=new_post.id, message=notification_message)
            db.session.add(notification)
        db.session.commit()

        flash('새로운 글이 성공적으로 작성되었습니다!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='새 글 작성', form=form)

@app.route('/notifications')
@login_required
def notifications():
    # 현재 사용자의 읽지 않은 알림을 먼저 가져옴
    unread_notifications = current_user.notifications_received.filter_by(is_read=False).order_by(Notification.timestamp.desc()).all()

    # 읽지 않은 알림들을 읽음 처리
    for notification in unread_notifications:
        notification.is_read = True
    db.session.commit() # 변경사항 저장

    # 사용자의 모든 알림을 다시 가져와서 화면에 표시 (읽음 처리된 상태 반영)
    all_user_notifications = current_user.notifications_received.order_by(Notification.timestamp.desc()).all()
    return render_template('notifications.html', notifications=all_user_notifications, title="알림 목록")

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
@login_required # 댓글 작성은 로그인이 필요하므로, 페이지 접근 자체를 로그인 필요로 변경
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()

    if form.validate_on_submit(): # POST 요청으로 댓글 작성 시
        if not current_user.is_authenticated: # 이중 체크 (보통 @login_required로 커버됨)
            flash('댓글을 작성하려면 로그인이 필요합니다.', 'warning')
            return redirect(url_for('login', next=url_for('view_post', post_id=post.id)))

        comment = Comment(content=form.content.data, post_id=post.id, user_id=current_user.id)
        db.session.add(comment)
        db.session.commit()
        flash('댓글이 성공적으로 작성되었습니다.', 'success')
        return redirect(url_for('view_post', post_id=post.id)) # 페이지 새로고침하여 댓글 표시

    # GET 요청 또는 폼 유효성 검사 실패 시
    comments = post.comments.order_by(Comment.timestamp.asc()).all() # 오래된 댓글부터
    return render_template('view_post.html', title=post.title, post=post, form=form, comments=comments)

# --- Helper Functions (Context Processors) ---
@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        unread_notifications_count = current_user.notifications_received.filter_by(is_read=False).count()
        return dict(unread_notifications_count=unread_notifications_count)
    return dict(unread_notifications_count=0)


# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # 데이터베이스 테이블 생성
    app.run(debug=True)
