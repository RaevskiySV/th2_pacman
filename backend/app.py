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


if __name__ == '__main__':
    app.run(port=8081)