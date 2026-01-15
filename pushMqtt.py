import os
import jwt
import json
import threading
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit, disconnect, join_room
from flask_cors import CORS

load_dotenv()

# -----------------------------
# Variáveis internas do módulo
# -----------------------------
_socketio: SocketIO | None = None
_mqtt_client = mqtt.Client()

_MQTT_BROKER = os.getenv("MQTT_BROKER")
_MQTT_PORT = int(os.getenv("MQTT_PORT"))
_MQTT_TOPIC = os.getenv("MQTT_TOPIC")
_MQTT_LOGIN = os.getenv("MQTT_LOGIN")
_MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# Sala especial (admin + gerente, ou o que o BD definir)
SYSTEM_WATCHERS_ROOM = "system_watchers"

if _MQTT_LOGIN and _MQTT_PASSWORD:
  _mqtt_client.username_pw_set(_MQTT_LOGIN, _MQTT_PASSWORD)

# -----------------------------
# Helpers
# -----------------------------
def _normalize_room(value: str) -> str:
  # Room names devem ser estáveis, sem espaços e previsíveis.
  return value.strip().lower().replace(" ", "_")
# def roles_to_rooms(roles):
#   mapping = {
#     "administrador": "admin",
#     "monitoramento": "monitoramento",
#   }

#   if isinstance(roles, str):
#     roles = [roles]

#   return [mapping[r] for r in roles if r in mapping]

# -----------------------------
# API pública do módulo
# -----------------------------
def init(app):
  """
  Inicializa Socket.IO, registra handlers e inicia MQTT.
  Essa função DEVE ser chamada pelo api.py.
  """
  global _socketio
  if _socketio is not None:
    return _socketio  # evita inicializar duas vezes

  # Socket.IO criado aqui
  _socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading"
  )

  def decode_jwt(token):
    try:
      payload = jwt.decode(
        token,
        app.config["JWT_SECRET_KEY"],
        algorithms=[app.config["JWT_ALGORITHM"]],
        issuer=app.config["JWT_ISSUER"],
        audience=app.config["JWT_AUDIENCE"],
        options={"require": ["exp", "iss", "aud", "sub"]}
      )
      return payload
    except Exception as e:
      print("JWT inválido:", e)
      return None

  # -------------------------
  # Socket.IO handlers
  # -------------------------
  @_socketio.on("connect")
  def on_socket_connect(auth):
    if not auth or "token" not in auth:
      print("passei aqui")
      disconnect()
      return

    payload = decode_jwt(auth["token"])
    if not payload:
      disconnect()
      return

    username = payload["sub"]
    roles = payload.get("roles", [])
    print(roles)

    # for room in roles_to_rooms(roles["nivelGerencia"]):
    #   join_room(room)
    user_type_room = _normalize_room(roles["nivelGerencia"])

    if user_type_room in ["gerente", "administrador"]:
      join_room(SYSTEM_WATCHERS_ROOM)

    emit("server_message", {
      "msg": f"Bem-vindo, {username}",
      "roles": roles["nivelGerencia"]
    })

  @_socketio.on("disconnect")
  def on_socket_disconnect():
    print("Socket desconectado")

  # -------------------------
  # MQTT handlers
  # -------------------------
  def on_mqtt_connect(client, userdata, flags, rc):
    print("MQTT conectado rc=", rc)
    client.subscribe(_MQTT_TOPIC)
    print("MQTT inscrito no tópico:", _MQTT_TOPIC)

  def on_mqtt_message(client, userdata, msg):
    if _socketio is None:
      return

    payload_str = msg.payload.decode(errors="replace")
    print("MQTT msg:", msg.topic, payload_str)

    try:
      data = json.loads(payload_str)
    except json.JSONDecodeError:
      data = {"raw": payload_str}

    event = {"topic": msg.topic, "data": data}

    # _socketio.emit(
    #   "access_message",
    #   event,
    #   room="monitoramento",
    #   namespace="/"
    # )

    _socketio.emit(
      "access_message",
      event,
      room=SYSTEM_WATCHERS_ROOM,
      namespace="/"
    )

  _mqtt_client.on_connect = on_mqtt_connect
  _mqtt_client.on_message = on_mqtt_message

  # -------------------------
  # MQTT thread
  # -------------------------
  def start_mqtt():
    print("Iniciando thread MQTT...")
    _mqtt_client.connect(_MQTT_BROKER, _MQTT_PORT, 60)
    _mqtt_client.loop_forever()

  threading.Thread(target=start_mqtt, daemon=True).start()

  return _socketio


def run_socketio(app):
  """
  Wrapper para rodar o servidor sem expor SocketIO fora do módulo.
  """
  if _socketio is None:
    raise RuntimeError("SocketIO não inicializado. Chame init_app(app, ...) primeiro.")
  # _socketio.run(app, **kwargs)
  _socketio.run(app, host="0.0.0.0", port=5000, debug=False, use_reloader=False)