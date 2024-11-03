from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sentry_sdk
from werkzeug.security import generate_password_hash, check_password_hash
import time
import random

# #############################################
# Configuration Flask
# #############################################
app = Flask(__name__)
app.secret_key = 'Log with Sentry'
app.template_folder = 'templates'


# #############################################
# Configuration Sentry
# #############################################
sentry_sdk.init(
    dsn="VOTRE DSN SENTRY",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0
)

# #############################################
# Configuration Login
# #############################################
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# #############################################
# Base de données simulée
# #############################################
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password


# #############################################
# Données de test
# #############################################
users = {}
tasks = []


def init_test_data():
    # Utilisateurs de test
    test_users = [
        {"id": 1, "username": "alice", "password": "test123"},
        {"id": 2, "username": "bob", "password": "test123"},
        {"id": 3, "username": "admin", "password": "admin123"}
    ]

    # Tâches de test
    test_tasks = [
        {"id": 1, "user_id": 1, "title": "Première tâche d'Alice", "completed": False},
        {"id": 2, "user_id": 1, "title": "Deuxième tâche d'Alice", "completed": True},
        {"id": 3, "user_id": 2, "title": "Tâche de Bob", "completed": False},
        {"id": 4, "user_id": 3, "title": "Tâche administrative", "completed": False}
    ]

    # Création des utilisateurs
    if not users:
        for user_data in test_users:
            users[user_data["id"]] = User(
                id=user_data["id"],
                username=user_data["username"],
                password=generate_password_hash(user_data["password"])
            )

            sentry_sdk.capture_message(
                f"Test user created: {user_data['username']}",
                level="info"
            )

    # Création des tâches
    if not tasks:
        tasks.extend(test_tasks)
        sentry_sdk.capture_message(
            f"Test tasks created: {len(test_tasks)} tasks",
            level="info"
        )


@login_manager.user_loader
def load_user(user_id):
    return users.get(int(user_id))


# #############################################
# Middleware pour le logging des requêtes
# Avant chaque requête, on log les informations de la requête
# #############################################
@app.before_request
def before_request():
    # #########################################################
    # Log de chaque requête
    # https://docs.sentry.io/platforms/python/enriching-events/breadcrumbs/
    # Sentry uses breadcrumbs to create a trail of events that happened prior to an issue.
    # These events are very similar to traditional logs, but can record more rich structured data.
    # #########################################################
    sentry_sdk.add_breadcrumb(
        category='request',
        message=f'Request to {request.endpoint}',
        level='info',
        data={
            'method': request.method,
            'path': request.path,
            'user': current_user.username if not current_user.is_anonymous else 'anonymous'
        }
    )
    # #########################################################


# #############################################
# Routes
# #############################################
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            if username in [u.username for u in users.values()]:
                raise ValueError("Username already exists")

            user_id = len(users) + 1
            users[user_id] = User(user_id, username, generate_password_hash(password))

            # #########################################################
            # Envoi d'un message contenant l'identité de l'utilisateur qui vient de s'inscrire à Sentry
            # #########################################################
            sentry_sdk.capture_message(
                f"New user registered: {username}",
                level="info",
                extras={"user_id": user_id}
            )
            # #########################################################

            return redirect(url_for('login'))

        except Exception as e:
            # #########################################################
            # Envoi d'un message contenant l'exception à Sentry
            # #########################################################
            sentry_sdk.capture_exception(e)
            # #########################################################

            flash('Registration failed')
            return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            user = next((u for u in users.values() if u.username == username), None)

            if user and check_password_hash(user.password, password):
                login_user(user)

                # #########################################################
                # Envoi d'un message contenant l'identité de l'utilisateur qui vient de se logger à Sentry
                # #########################################################
                sentry_sdk.set_user({"id": user.id, "username": user.username})
                # #########################################################

                return redirect(url_for('dashboard'))
            else:
                raise ValueError("Invalid credentials")

        except Exception as e:

            # #########################################################
            # Envoi d'un message contenant l'exception à Sentry
            # #########################################################
            sentry_sdk.capture_exception(e)
            # #########################################################

            flash('Login failed')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():

    # Simulation d'une opération lente aléatoire
    if random.random() < 0.1:  # 10% de chance
        time.sleep(2)

        # #########################################################
        # Envoi d'un message d'avertissement à Sentry
        # #########################################################
        sentry_sdk.capture_message(
            "Slow dashboard load detected",
            level="warning"
        )
        # #########################################################

    with sentry_sdk.start_span(op="task_loading"):
        user_tasks = [task for task in tasks if task['user_id'] == current_user.id]

    return render_template('dashboard.html', tasks=user_tasks)


@app.route('/task/create', methods=['POST'])
@login_required
def create_task():
    try:
        title = request.form.get('title')
        if not title:
            raise ValueError("Task title is required")

        task = {
            'id': len(tasks) + 1,
            'user_id': current_user.id,
            'title': title,
            'completed': False
        }

        tasks.append(task)

        # #########################################################
        # Envoi d'un message contenant l'info de l'action à Sentry
        # #########################################################
        sentry_sdk.add_breadcrumb(
            category='task',
            message=f'Task created: {title}',
            level='info'
        )
        # #########################################################

        return redirect(url_for('dashboard'))

    except Exception as e:
        sentry_sdk.capture_exception(e)
        flash('Failed to create task')
        return redirect(url_for('dashboard'))


@app.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    try:
        task = next((t for t in tasks if t['id'] == task_id), None)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task['user_id'] != current_user.id:
            raise PermissionError("Not authorized to modify this task")

        task['completed'] = not task['completed']

        # #########################################################
        # Envoi d'un message contenant l'info de l'action à Sentry
        # ################################################
        sentry_sdk.add_breadcrumb(
            category='task',
            message=f'Task {task_id} toggled to {task["completed"]}',
            level='info'
        )
        # #########################################################

        return redirect(url_for('dashboard'))

    except Exception as e:
        sentry_sdk.capture_exception(e)
        flash('Failed to update task')
        return redirect(url_for('dashboard'))


@app.route('/error')
def trigger_error():
    # Route de démonstration pour générer différentes erreurs
    error_type = request.args.get('type', 'division')

    if error_type == 'division':
        1 / 0
    elif error_type == 'key':
        {}['nonexistent']
    elif error_type == 'type':
        len(None)
    else:
        raise Exception("Generic error")


@app.route('/logout')
@login_required
def logout():
    sentry_sdk.add_breadcrumb(
        category='auth',
        message=f'User logged out: {current_user.username}',
        level='info'
    )
    logout_user()
    flash('Vous avez été déconnecté.')
    return redirect(url_for('index'))
# #############################################


# #############################################
# Main
# #############################################
if __name__ == '__main__':
    try:
        init_test_data()
        print("Données de test initialisées avec succès!")
        print("\nUtilisateurs de test :")
        print("------------------------")
        print("username: alice, password: test123")
        print("username: bob,   password: test123")
        print("username: admin, password: admin123\n")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print("Erreur lors de l'initialisation des données de test:", str(e))

    app.run(debug=True)
