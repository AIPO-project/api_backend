import os
import json
import threading
from flask_socketio import SocketIO, emit, disconnect, join_room
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

_socketio = None
_mqtt_client = mqtt.Client()
_app = None

_MQTT_BROKER = os.getenv("MQTT_BROKER")
_MQTT_PORT = int(os.getenv("MQTT_PORT"))
_MQTT_TOPIC = os.getenv("MQTT_TOPIC")
_MQTT_LOGIN = os.getenv("MQTT_LOGIN")
_MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

if _MQTT_LOGIN and _MQTT_PASSWORD:
  _mqtt_client.username_pw_set(_MQTT_LOGIN, _MQTT_PASSWORD)

# def init(app):
#   _socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
#   _app = app

def decode_jwt(token: str, JWT_SECRET, JWT_ISSUER, JWT_AUDIENCE) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iss", "aud", "sub"]}
        )
        return payload
    except Exception as e:
        print("JWT inválido:", e)
        return None
    
def roles_to_rooms(roles: list[str]) -> list[str]:
    # Mapeie roles -> rooms
    # Ex.: quem tem role "admin" entra em room "admins"
    # Essa função deverá receber uma lista que deverá vir do banco
    # Essa lista atualmente possui administrador, gerente e usuário
    mapping = {
        "admin": "admins",
        "portaria": "portaria",
        "monitoramento": "monitoramento",
    }
    rooms = []
    for r in roles:
        if r in mapping:
            rooms.append(mapping[r])
    return rooms

# -----------------------------
# Socket.IO auth + rooms
# -----------------------------
@_socketio.on("connect")
def on_socket_connect(auth):
    """
    O cliente deve conectar com:
    io(url, { auth: { token: "..." } })
    """
    if not auth or "token" not in auth:
        print("Conexão recusada: sem token")
        disconnect()
        return

    token = auth.get("token")
    payload = decode_jwt(token)
    if not payload:
        print("Conexão recusada: token inválido")
        disconnect()
        return

    username = payload["sub"]
    roles = payload.get("roles", [])
    print(f"Socket conectado: user={username} roles={roles}")

    # Entra nas rooms conforme roles
    for room in roles_to_rooms(roles):
        join_room(room)

    emit("server_message", {"msg": f"Bem-vindo, {username}!", "roles": roles})

@_socketio.on("disconnect")
def on_socket_disconnect():
    print("Socket desconectado")

def on_mqtt_connect(client, userdata, flags, rc):
  print("MQTT conectado rc=", rc)
  client.subscribe(_MQTT_TOPIC)
  print("MQTT inscrito no tópico:", _MQTT_TOPIC)

def on_mqtt_message(client, userdata, msg):
  try:
    payload_str = msg.payload.decode(errors="replace")
    print("MQTT msg:", msg.topic, payload_str)

    try:
      data = json.loads(payload_str)
    except json.JSONDecodeError:
      data = {"raw": payload_str}

    event = {"topic": msg.topic, "data": data}

    # Exemplo de regra de autorização:
    # - Só "monitoramento" recebe eventos de acesso
    # - Só "admins" recebe eventos completos (ou extras)
    _socketio.emit("mqtt_message", event, room="monitoramento", namespace="/")

    # opcional: admins recebem também
    # _socketio.emit("mqtt_message_admin", event, room="admins", namespace="/")

    print("Emit OK -> rooms monitoramento/admins")
  except Exception as e:
    print("Erro no on_mqtt_message:", e)

_mqtt_client.on_connect = on_mqtt_connect
_mqtt_client.on_message = on_mqtt_message

def start_mqtt():
  print("Iniciando thread MQTT...")
  _mqtt_client.connect(_MQTT_BROKER, _MQTT_PORT, keepalive=60)
  _mqtt_client.loop_forever()

def start(app):
  # IMPORTANTE: garantir 1 processo
  mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
  mqtt_thread.start()

  _socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
  _app = app

  _socketio.run(_app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)