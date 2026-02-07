import random
import json
import generate_qr
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)


def is_game_started():
    return 0 <= game_state['current_question_index'] < len(questions)


# Load questions from JSON file
with open('questions.json', 'r') as f:
    all_questions = json.load(f)['questions']

# Add 'correct' index to each question (assuming first answer is correct)
for q in all_questions:
    q['correct'] = 0

questions = []  # This will hold the 5 questions for the current game


@app.route('/')
def index():
    return render_template('index.html')


def stop_timer_thread():
    if game_state.get('timer_thread'):
        game_state['timer_thread'].cancel()
        game_state['timer_thread'] = None


def add_scores_for_correct_answers():
    current_q = questions[game_state['current_question_index']]
    correct_answer_index = current_q['correct']

    # Set intermission duration: 5s if 1 player, else 10s
    intermission_duration = 5 if len(game_state['players']) == 1 else 10
    game_state['intermission_duration'] = intermission_duration

    # Prepare results for host screen
    results = {
        'next_question_time': time.time() + intermission_duration,
        'question': current_q['question'],
        'answers': current_q['answers'],
        'correct_index': correct_answer_index,
        'player_answers': {}
    }

    for _sid, answer_data in game_state['current_answers'].items():
        username = answer_data['username']
        chosen_answer_index = answer_data['answer_index']
        answer_time = answer_data.get('time', time.time())

        results['player_answers'][username] = {
            'chosen_index': chosen_answer_index,
            'is_correct': (chosen_answer_index == correct_answer_index)
        }
        if chosen_answer_index == correct_answer_index:
            # Score based on time remaining (end_time - answer_time)
            time_left = max(
                0, int(
                    game_state.get(
                        'end_time', time.time()) - answer_time))
            game_state['players'][username]['score'] += (100 + time_left)

    socketio.emit('round_results', results)
    send_player_details()


def process_answers():
    if game_state.get('answers_processed'):
        return
    game_state['answers_processed'] = True
    stop_timer_thread()

    # Calculate scores first to set intermission_duration
    add_scores_for_correct_answers()
    game_state['current_answers'] = {}

    # Start intermission timer
    duration = game_state.get('intermission_duration', 20)
    game_state['intermission_active'] = True
    game_state['intermission_timer_thread'] = threading.Timer(
        duration, auto_next_question, args=[
            game_state['current_question_index'] + 1])
    game_state['intermission_timer_thread'].start()


def resolve_scores():
    sorted_players = sorted(
        game_state['players'].items(),
        key=lambda item: item[1]['score'],
        reverse=True)
    winning_players_list = []
    if sorted_players:
        top_score = sorted_players[0][1]['score']
        if top_score == 0:
            top_score += 1  # Prevent all zero score winners
        winning_players_list = [
            player[0] for player in sorted_players if player[1]['score'] == top_score]
    return sorted_players, winning_players_list


def send_player_details():
    sorted_players, winning_players_list = resolve_scores()
    socketio.emit('player_list', {
        'players': dict(sorted_players),
        'winning_players': winning_players_list
    })


def auto_next_question(target_index):
    with app.app_context():
        next_question(target_index)


@socketio.on('connect')
def test_connect():
    print('Client connected')
    send_player_details()


@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')


@socketio.on('join')
def handle_join(data):
    username = data['username']
    client_ip = request.remote_addr

    if username not in game_state['players']:
        game_state['players'][username] = {
            'score': 0,
            'sid': request.sid,
            'ip': client_ip
        }
        join_room(username)
        emit('joined', {'username': username})  # Emit to the joining player
        print(f'{username} joined the game from {client_ip}.')
    else:
        # Check if it's the same user re-joining
        if game_state['players'][username].get('ip') == client_ip:
            game_state['players'][username]['sid'] = request.sid
            join_room(username)
            emit('joined', {'username': username})
            print(f'{username} re-joined the game from {client_ip}.')
        else:
            emit('error', {'message': 'Username already taken.'})
            return

    send_player_details()

    if is_game_started():
        index = game_state['current_question_index']
        question_data = questions[index]
        # Send index to allow frontend to track it
        emit('question', {**question_data, 'index': index})
        if game_state.get('end_time') and game_state['end_time'] > time.time():
            emit('timer', game_state['end_time'])


@socketio.on('typing_username')
def handle_typing(data):
    username = data.get('username', '').strip()
    print(f"DEBUG: Received typing_username from {request.sid}: '{username}'")
    if username:
        # Check if joining_players exists in game_state, if not initialize it
        # or ignore
        if 'joining_players' in game_state:
            game_state['joining_players'][request.sid] = username


def reset_game():
    game_state['current_question_index'] = -1  # Reset for first question
    game_state['current_answers'] = {}
    for player in game_state['players']:
        game_state['players'][player]['score'] = 0  # Reset scores

    # Select 5 random questions for the game
    random.shuffle(all_questions)
    global questions
    questions = all_questions[:5]  # Take the first 5 questions


@socketio.on('start_game')
def start_game():
    socketio.emit('game_started')
    next_question(0)


game_state = None


@socketio.on('reset_all')
def reset_all():
    global game_state

    if game_state is None:
        game_state = {}

    stop_timer_thread()
    # if 'players' not in game_state:
    game_state['players'] = {}

    reset_game()

    socketio.emit('game_reset')
    send_player_details()
    print('Game and players fully reset.')


@socketio.on('answer')
def handle_answer(data):
    username = data['username']
    answer_index = data['answer_index']

    # Check if timer is running (end_time > now)
    if game_state.get('end_time') and time.time(
    ) < game_state['end_time'] and username in game_state['players']:
        game_state['current_answers'][request.sid] = {
            'username': username,
            'answer_index': answer_index,
            'time': time.time()
        }
        print(f'{username} answered: {answer_index}')

        # Check if all active players have answered
        if len(game_state['current_answers']) == len(game_state['players']):
            process_answers()


@socketio.on('next_question')
def next_question(question_index):

    if question_index <= game_state['current_question_index']:
        return  # Ignore if same question index or irregular jump back

    # Check if intermission is active (manual skip)
    if game_state.get('intermission_active'):
        game_state['intermission_active'] = False
        if game_state.get('intermission_timer_thread'):
            game_state['intermission_timer_thread'].cancel()

    print(f'Moving to question index: {question_index}')
    if game_state['current_question_index'] != -1:
        process_answers()

    game_state['current_question_index'] = question_index
    game_state['current_answers'] = {}  # Clear answers for new question
    game_state['answers_processed'] = False

    if game_state['current_question_index'] < len(questions):
        question_data = questions[game_state['current_question_index']]

        # Get correct answer text before mutation
        correct_answer_text = question_data['answers'][question_data['correct']]

        # Separate correct and incorrect
        incorrect_answers = [
            a for i, a in enumerate(
                question_data['answers']) if i != question_data['correct']]

        # Limit to 3 random incorrect answers if there are more
        if len(incorrect_answers) > 3:
            incorrect_answers = random.sample(incorrect_answers, 3)

        # Combine and shuffle
        new_answers = [correct_answer_text] + incorrect_answers
        random.shuffle(new_answers)

        # Update the question object directly
        question_data['answers'] = new_answers
        question_data['correct'] = new_answers.index(correct_answer_text)

        # Include index in payload
        socketio.emit(
            'question', {
                **question_data, 'index': game_state['current_question_index']})

        game_state['end_time'] = time.time() + 30
        game_state['timer_thread'] = threading.Timer(30, process_answers)
        game_state['timer_thread'].start()
        socketio.emit('timer', game_state['end_time'])
        print(f'Question {game_state["current_question_index"] + 1} started.')
    else:
        game_state['game_started'] = False  # End game
        socketio.emit('game_over', game_state['players'])
        print('Game over!')


if __name__ == '__main__':
    generate_qr.generate_qr()
    reset_all()
    socketio.run(
        app,
        debug=True,
        host='0.0.0.0',
        port=9145,
        allow_unsafe_werkzeug=True)
