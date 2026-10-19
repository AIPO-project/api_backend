import hmac
import os
from datetime import datetime
from flask import Blueprint, current_app, jsonify, request


def create_mqtt_blueprint(mysql):
    bp = Blueprint('mqtt_access', __name__)

    @bp.post('/internal/mqtt/acesso')
    def process_access():
        expected = os.getenv('MQTT_API_TOKEN', '')
        supplied = request.headers.get('X-Service-Token', '')
        if not expected or not hmac.compare_digest(expected, supplied):
            return jsonify(status='error', erro='unauthorized'), 401

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(status='error', erro='invalid_json'), 400
        chave, fechadura = data.get('idChave'), data.get('idFechadura')
        if not all(isinstance(x, str) and x.strip() and len(x) <= 255 for x in (chave, fechadura)):
            return jsonify(status='error', erro='invalid_fields'), 400

        cur = None
        try:
            conn = mysql.connection
            cur = conn.cursor()
            cur.execute('SELECT matricula FROM usuarios WHERE chave = %s LIMIT 1', (chave,))
            usuario = cur.fetchone()
            cur.execute('SELECT id FROM salas WHERE fechadura = %s LIMIT 1', (fechadura,))
            sala = cur.fetchone()
            cur.execute('''SELECT 1 FROM autorizacao aut
                JOIN usuarios us ON us.id = aut.id_usuario
                JOIN salas s ON s.id = aut.id_sala
                WHERE us.ativo = 1 AND s.ativo = 1
                AND s.fechadura = %s AND us.chave = %s LIMIT 1''', (fechadura, chave))
            autorizado = cur.fetchone() is not None
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            acesso_id = None
            if usuario and sala:
                cur.execute('''INSERT INTO acessos (usuario, sala, timestamp, autorizado)
                               VALUES (%s, %s, %s, %s)''',
                            (usuario[0], sala[0], timestamp, int(autorizado)))
                acesso_id = cur.lastrowid
                conn.commit()

            if not sala:
                frontend = {'erro': True, 'timestamp': timestamp}
            elif usuario:
                frontend = {'erro': False, 'chaveCadastrada': True, 'id': acesso_id, 'timestamp': timestamp}
            else:
                frontend = {'erro': False, 'chaveCadastrada': False, 'timestamp': timestamp}
            return jsonify(status='ok', autorizado=autorizado, frontend=frontend)
        except Exception:
            current_app.logger.exception('Falha no processamento de acesso MQTT')
            try:
                mysql.connection.rollback()
            except Exception:
                pass
            return jsonify(status='error', erro='database_error'), 503
        finally:
            if cur is not None:
                cur.close()

    return bp
