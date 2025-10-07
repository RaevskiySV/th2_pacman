import os

from flask import Flask, jsonify, request
from flask_cors import CORS
import redis


app = Flask(__name__)
CORS(app)

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
LEADERBOARD_KEY = 'global_leaderboard'

try:
    r = redis.StrictRedis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True
    )
    r.ping()
    app.logger.info(f'Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}')
except redis.exceptions.ConnectionError as e:
    app.logger.error(f'FATAL: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Error: {e}')


@app.route('/api/saveScore', methods=['POST'])
def save_score():
    try:
        data = request.get_json()

        if not data:
            app.logger.warning('Request failed: No JSON data received.')
            return jsonify({'status': 'error', 'message': 'No data'}), 400

        name = data.get('name')
        email = data.get('email')
        score = data.get('score')

        if not name or not email or not score:
            app.logger.warning('Request failed: Missing name, email, or score in data.')
            return jsonify({'status': 'error', 'message': 'Not enough data'}), 400

        try:
            score = int(score)
        except ValueError:
            app.logger.warning(f'Request failed: Invalid score value: {score}.')
            return jsonify({'status': 'error', 'message': 'Score must be an integer'}), 400

        r.zadd(LEADERBOARD_KEY, {email: score})

        user_hash_key = f'user:{email}'
        r.hset(user_hash_key, mapping={'name': name, 'score': score})

        app.logger.info(f'Request successful.')

        return jsonify({
            'status': 'success',
            'received_name': name,
            'received_email': email,
            'received_score': score
        }), 200

    except redis.exceptions.RedisError as re:
        app.logger.error(f'Redis operation failed: {re}')
        return jsonify({'status': 'error', 'message': 'Database error'}), 500

    except Exception as e:
        app.logger.exception(f'An unexpected error occurred in save_score: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


def get_leaderboard_data(start_index, end_index):
    raw_leaderboard = r.zrevrange(
        LEADERBOARD_KEY,
        start_index,
        end_index,
        withscores=True
    )

    if not raw_leaderboard:
        return []

    pipe = r.pipeline()
    for email, _ in raw_leaderboard:
        user_hash_key = f"user:{email}"
        pipe.hget(user_hash_key, 'name')

    names = pipe.execute()

    leaderboard = []

    for rank_index, ((email, score), name) in enumerate(zip(raw_leaderboard, names)):
        leaderboard.append({
            "rank": rank_index + start_index + 1,
            "email": email,
            "name": name if name else "Unknown",
            "score": int(score)
        })

    return leaderboard


@app.route('/api/getTop1', methods=['GET'])
def get_top_1():
    try:
        top_player = get_leaderboard_data(0, 0)

        if not top_player:
            return jsonify({"status": "success", "message": "No scores yet.", "player": []}), 200

        return jsonify({
            "status": "success",
            "message": "Successfully retrieved top-1 player.",
            "player": top_player[0]
        }), 200

    except Exception as e:
        app.logger.exception(f"Error retrieving top-1 player: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/getLeaderboard', methods=['GET'])
def get_leaderboard():
    try:
        top_10 = get_leaderboard_data(0, 9)

        if not top_10:
            return jsonify({"status": "success", "message": "No scores yet.", "leaderboard": []}), 200

        return jsonify({
            "status": "success",
            "message": "Successfully retrieved leaderboard.",
            "leaderboard": top_10
        }), 200

    except Exception as e:
        app.logger.exception(f"Error retrieving leaderboard: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/getAll', methods=['GET'])
def get_all_data():
    try:
        all_data = get_leaderboard_data(0, -1)

        if not all_data:
            return jsonify({"status": "success", "message": "No scores yet.", "data": []}), 200

        return jsonify({
            "status": "success",
            "message": "Successfully retrieved all data.",
            "data": all_data
        }), 200

    except Exception as e:
        app.logger.exception(f"Error retrieving all data: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(port=8081)