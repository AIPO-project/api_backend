import time
import json
from flask import Flask
from flask import request
import requests
from flask_cors import CORS
from flask_mysqldb import MySQL
import serial
from datetime import datetime

import logging
import os #utilizado para pegar os valores que estão na variável de ambiente
from dotenv import load_dotenv
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity, get_jwt

app = Flask(__name__)
CORS(app)
load_dotenv() #carrega as variveis de ambiente

logger = logging.getLogger("AIPO_API")
logging.basicConfig(filename='allLogs.log', encoding='ISO-8859-1', level=logging.DEBUG)

# logging.basicConfig(format='%(levelname)s:%(message)s', encoding='utf-8', level=logging.DEBUG)

# handle para lidar com o terminal
terminal_logger = logging.StreamHandler()
terminal_logger.setLevel(logging.DEBUG)

# handle para lidar com o arquivo
file_logger = logging.FileHandler("api.log", encoding='ISO-8859-1')
file_logger.setLevel(logging.WARNING)

# create formatter
formatter = logging.Formatter('%(name)s:%(levelname)s \t- - %(asctime)s %(message)s', datefmt='[%d/%m/%Y %H:%M:%S]')

# add formatter to handles
terminal_logger.setFormatter(formatter)
file_logger.setFormatter(formatter)

# add handles to logger
logger.addHandler(terminal_logger)
logger.addHandler(file_logger)

app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")
app.config['MYSQL_DB'] = os.getenv("MYSQL_DATABASE")
app.config['MYSQL_PORT'] = int(os.getenv("MYSQL_PORT"))
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

jwt = JWTManager(app)
mysql = MySQL(app)
token_refresh =""

def log_database(funcaoAPI, usuarioAtingido, descricao):
  usuarioAtual = get_jwt_identity()
  claims = get_jwt()
  roles = claims.get("roles")
  nivelGerencia = roles["nivelGerencia"]

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))

  sql = " INSERT INTO dataLog (usuarioAcao, tipoAcao, alvoAcao, descricao, nivelGerencia) VALUES (%s, %s, %s, %s, %s)"
  dados = (usuarioAtual, funcaoAPI, usuarioAtingido, descricao, nivelGerencia)
  
  try:
    cur.execute(sql, dados)
    mysql.connection.commit()
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))

  cur.close()

@jwt.expired_token_loader
def my_expired_token_callback(jwt_header, jwt_payload):
    return {"status":"Token has expired"}, 401

# Usado unica e exclusivamente para testes
@app.route('/time')
def get_current_time():
  # logger.debug("teste")
  return {'time': time.time()}

# @app.route('/usuarios_free', methods = ['GET', 'POST'])
# def get_usuarios():
#   return get_data()

# Usado para retornar lista de usuários
@app.route('/usuarios', methods = ['GET', 'POST'])
@jwt_required()
def get_data():
  if request.method == 'GET':
    try:
      cur = mysql.connection.cursor()
    except Exception as e:
      logger.warning(str(e))
      return {"status":str(e)}
    
    try:
      cur.execute('''SELECT * FROM usuarios''')
    except Exception as e:
      cur.close()
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}
 
    columns = [column[0] for column in cur.description]
    data = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()

    return data

# Usado para adicionar um novo usuário ao banco
@app.route('/adicionarUsuarios', methods = [ 'POST'])
@jwt_required()
def add_data():
  
  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  # logger.debug (request.json)
  nome          = request.json["nome"]
  matricula     = request.json["matricula"]
  tipoUsuario   = request.json['tipoUsuario']
  nivelGerencia = request.json['nivelGerencia']
  #            insert into usuarios (matricula, nome, tipoUsuario, nivelGerencia) values ("  009876   ","   len","             ","               ")
  sql =       ("insert into usuarios (matricula, nome, tipoUsuario, nivelGerencia) values (%s,%s,%s,%s)")
  d = (matricula, nome, tipoUsuario, nivelGerencia)
  # logger.debug(sql % d)

  try:
    cur.execute(sql, d)
    mysql.connection.commit()
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  cur.close()

  log_database("adicionarUsuarios", matricula, "")
  
  return {"status":"ok"}

# Usado para adicionar um novo usuário ao banco
@app.route('/procurarUsuarioSUAP/<matricula>', methods = [ 'GET'])
def procurarUsuarioSUAP(matricula):
  global token_refresh

  api_url_refresh = "https://suap.ifrn.edu.br/api/token/refresh"

  payload = {"refresh": token_refresh}
  response_refresh = requests.post(api_url_refresh, json=payload)

  if response_refresh.status_code == 200:

    token = response_refresh.json()["access"]
    token_refresh = response_refresh.json()["refresh"]

    api_url = "https://suap.ifrn.edu.br/api/edu/dados-aluno-matriculado/?matricula="+matricula

    headers = {
      "Authorization": f'Bearer {token}'
    }

    response_meus_dados = requests.get(api_url, headers=headers)

    if response_meus_dados.status_code == 200:
      print("Comunicação deu certo:") 
      print(response_meus_dados.json()["nome"])
      nome = response_meus_dados.json()["nome"]
      matricula = response_meus_dados.json()["matricula"]

      return {"status":"ok", "dados": {"matricula":matricula, "nome":nome}}
    elif response_meus_dados.status_code == 400 or response_meus_dados.status_code == 404:
      print("passei aqui")
      return {"status":"usuário não encontrado", "erro":response_meus_dados.status_code}
    else:
      return {"status":response_meus_dados.status_code}
  return {"status":response_refresh.status_code}

# Usado para retornar uma lista de salas autorizadas para usuarios
@app.route('/UsuariosSalas', methods = ['GET'])
def get_usuarios_salas():

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  sql = "SELECT  matricula AS usuarios, codigo AS salas FROM usuarios u "
  sql += "JOIN autorizacao aut ON u.id = aut.id_usuario "
  sql += "JOIN salas s ON aut.id_sala = s.id"

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]

  temp={}

  for d in data:
    temp[d["usuarios"]] = []
  
  for d in data:
    temp[d["usuarios"]].append(d["salas"])

  cur.close()

  return temp

# Usado para retornar uma lista de usuarios autorizados para uma sala
@app.route('/getUsuariosPorSala/<codigo_sala>', methods = ['GET'])
def getUsuariosPorSala(codigo_sala):

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  # sql = "SELECT  u.matricula, u.nome, u.tipoUsuario, u.nivelGerencia, u.ativo FROM usuarios u "
  # sql += "JOIN autorizacao aut ON u.id = aut.id_usuario "
  # sql += "JOIN salas s ON aut.id_sala = s.id"

  sql =  "SELECT  u.matricula, u.nome, u.tipoUsuario, u.nivelGerencia, u.ativo FROM usuarios u "
  sql += "JOIN autorizacao aut ON u.id = aut.id_usuario JOIN salas s ON aut.id_sala = s.id "
  sql += "where s.codigo='"+codigo_sala+"' and (aut.data_limite is NULL or  NOW() < aut.data_limite) "
  sql += "and (aut.horario_inicio is NULL or aut.horario_inicio = '00:00:00')"
  sql += "and (aut.horario_fim is NULL or aut.horario_fim = '23:59:59')"

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  columns = [column[0] for column in cur.description]
  acessoTodosHorarios = [dict(zip(columns, row)) for row in cur.fetchall()]

  sql =  "SELECT  u.matricula, u.nome, u.tipoUsuario, u.nivelGerencia, u.ativo FROM usuarios u "
  sql += "JOIN autorizacao aut ON u.id = aut.id_usuario JOIN salas s ON aut.id_sala = s.id "
  sql += "where s.codigo='"+codigo_sala+"' and (aut.data_limite is NULL or  NOW() < aut.data_limite) "
  sql += "and ((aut.horario_inicio is not NULL and aut.horario_inicio != '00:00:00')"
  sql += "or (aut.horario_fim is not NULL and aut.horario_fim != '23:59:59'))"
  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  columns = [column[0] for column in cur.description]
  acessoHorariosLimitados = [dict(zip(columns, row)) for row in cur.fetchall()]

  data = {"allHours": acessoTodosHorarios, "limitedHours": acessoHorariosLimitados}

  # logger.debug(data)

  # for d in data:
  #   temp[d["usuarios"]] = []
  
  # for d in data:
  #   temp[d["usuarios"]].append(d["salas"])

  cur.close()

  return data


# Usado para retornar uma lista de usuarios não autorizados para uma sala
@app.route('/getUsuariosForaSala/<codigo_sala>', methods = ['GET'])
def getUsuariosForaSala(codigo_sala):

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  # sql = "SELECT  u.matricula, u.nome, u.tipoUsuario, u.nivelGerencia, u.ativo FROM usuarios u "
  # sql += "JOIN autorizacao aut ON u.id = aut.id_usuario "
  # sql += "JOIN salas s ON aut.id_sala = s.id"
  # logger.debug(codigo_sala)
  sql =  "SELECT  u.matricula, u.nome, u.tipoUsuario, u.nivelGerencia, u.ativo FROM usuarios u "
  sql += "JOIN autorizacao aut ON u.id = aut.id_usuario JOIN salas s ON aut.id_sala = s.id "
  sql += "where s.codigo!='"+codigo_sala+"' or (s.codigo='"+codigo_sala+"' "
  sql += "and (aut.data_inicio > NOW() or aut.data_limite < NOW() ))"

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]

  # temp={}

  # logger.debug(data)

  # for d in data:
  #   temp[d["usuarios"]] = []
  
  # for d in data:
  #   temp[d["usuarios"]].append(d["salas"])

  cur.close()

  return data

# Usado para retornar uma lista de usuarios não autorizados para uma sala
@app.route('/getUsuariosNaoAutorizados/<codigo_sala>', methods = ['GET'])
def getUsuariosNaoAutorizados(codigo_sala):

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  # sql = "SELECT  u.matricula, u.nome, u.tipoUsuario, u.nivelGerencia, u.ativo FROM usuarios u "
  # sql += "JOIN autorizacao aut ON u.id = aut.id_usuario "
  # sql += "JOIN salas s ON aut.id_sala = s.id"

  sql =  "SELECT  u.matricula, u.nome, u.tipoUsuario, u.nivelGerencia, u.ativo FROM usuarios u "
  sql += "JOIN autorizacao aut ON u.id = aut.id_usuario JOIN salas s ON aut.id_sala = s.id "
  sql += "where s.codigo='"+codigo_sala+"' and (aut.data_limite is NULL or NOW() < aut.data_limite)"

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  columns = [column[0] for column in cur.description]
  usuariosAutorizados = [dict(zip(columns, row)) for row in cur.fetchall()]

  try:
    cur.execute('''SELECT * FROM usuarios''')
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  columns = [column[0] for column in cur.description]
  todosUsuarios = [dict(zip(columns, row)) for row in cur.fetchall()]
  
  data = []

  for usuario in todosUsuarios:
    data.append(usuario)
    for usarioAutorizado in usuariosAutorizados:
      if usuario["matricula"] == usarioAutorizado["matricula"] :
        data.remove(usuario)
        break

  cur.close()

  return {"status":"ok", "dados":data}

# Usado para retornar,modificar dados de um usuário ou deletar um usuário
@app.route('/usuario/<user_id>', methods = ['GET', 'PUT', 'DELETE'])
def data(user_id):

  if request.method == 'GET':
    try:
      cur = mysql.connection.cursor()
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}

    sql = "SELECT * FROM usuarios WHERE matricula='"+user_id+"'"
    try:
      cur.execute(sql)
    except Exception as e:
      cur.close()
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}
    columns = [column[0] for column in cur.description]
    data = [dict(zip(columns, row)) for row in cur.fetchall()]

    # logger.debug(str(data))

    return {"status": "ok", "data": data}
  if request.method == 'DELETE':
    try:
      cur = mysql.connection.cursor()
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}

    sql = ("DELETE FROM usuarios WHERE matricula='"+user_id+"'")
    logger.debug(sql)

    try:
      cur.execute(sql)
      mysql.connection.commit()
    except Exception as e:
      cur.close()
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}

    return {"resultado":{"status":"ok"}}

  if request.method == 'PUT':

    data = request.json

    try:
      cur = mysql.connection.cursor()
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}

    sql  = "UPDATE usuarios SET "
    sql += "nome='" + data["nome"] +"', matricula='"+data["matr"]+"'"
    sql += ", ativo='"+ str(data["usuarioAtivo"]) +"'"
    sql += ", tipoUsuario='"+ data["tipoUsuario"] +"', nivelGerencia='"+ data["tipoGerencia"] +"'"
    sql += " WHERE matricula='"+user_id+"'"

    logger.debug(sql)

    try:
      cur.execute(sql)
      mysql.connection.commit()
    except Exception as e:
      logger.warning(str(e))
      return {"status":str(e)}
    
    return {"status":"ok"}
  
@app.route('/serialAvailable', methods = ['GET'])
def serialAvailable():
  try:
    portaSerial = serial.Serial('/dev/ttyUSB0', 115200)
  except:
    return {"status":"problemas ao abrir a porta serial"}
  return  {"status":"ok"}

@app.route('/setChave/<user_id>', methods = ['PUT'])
def setChave2(user_id):
  try:
    data = request.json
  except Exception as e:  
    logger.warning("dados não enviados pelo cliente: "+str(e))
    return {"status":str(e)}
  
  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}
  
  chave = data["chave"]
  # logger.debug(chave)
  # chave = "AA AA AA CC"

  sql  = "UPDATE usuarios SET chave='"+ chave +"' WHERE matricula="+user_id
  logger.debug(sql)

  try:
    cur.execute(sql)
    mysql.connection.commit()
  except Exception as e:
    cur.close()
    logger.debug(str(e))
    return {"status": str(e)}    

  cur.close()
  
  return {"status":"ok"}


# Utilizado para atualizar a chave de um usuário
@app.route('/chave/<user_id>', methods = ['PUT'])
def setChave(user_id):
  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  try:
    portaSerial = serial.Serial('/dev/ttyUSB0', 115200)
  except:
    return {"status":"problemas ao abrir a porta serial"}

  
  if portaSerial.isOpen():
    try:
      portaSerial.write(b's');
      incoming = portaSerial.readline()
    except Exception as e:
      logger.warning(str(e))
      return {"status":str(e)}
    portaSerial.close()
  else:
    return {"status": "porta serial fechada"}
  
  data = json.loads(incoming)

  chave = data["chave"]
  # chave = "AA AA AA CC"

  sql  = "UPDATE usuarios SET chave='"+ chave +"' WHERE matricula="+user_id
  logger.debug(sql)

  try:
    cur.execute(sql)
    mysql.connection.commit()
  except Exception as e:
    cur.close()
    logger.debug(str(e))
    return {"status": str(e)}    

  cur.close()
  

  return {"status":"ok"}

# Utilizado para remover a chave de um usuário
@app.route('/chave/<user_id>', methods = ['DELETE'])
def deleteChave(user_id):
  if request.method == 'DELETE':
    try:
      cur = mysql.connection.cursor()    
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}
    # update usuarios set chave = NULL where matricula = '20231170150017';

    sql = ("UPDATE usuarios SET chave = NULL WHERE matricula='"+user_id+"'")
    logger.debug(sql)

    try:
      cur.execute(sql)
      mysql.connection.commit()
    except Exception as e:
      cur.close()
      logger.warning(str(e))
      return {"status": str(e)}    


    return {"status":"ok"}    

# retorna a lista de salas
@app.route('/salas', methods = ['GET'])
def getSalas():
  if request.method == 'GET':
    try:
      cur = mysql.connection.cursor()
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}
  
    try:
      cur.execute('''SELECT * FROM salas''')
    except Exception as e:
      cur.close()
      logger.warning(str(e))
      return {"status":str(e)}

    columns = [column[0] for column in cur.description]
    data = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()

    return data

# adiciona uma nova sala ao banco
@app.route('/adicionarSala', methods = [ 'POST'])
@jwt_required()
def add_sala():
  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  logger.debug(request.json)
  nome          = request.json["nome"]
  codigo     = request.json["codigo"]
  local   = request.json['local']
  fechadura = request.json['fechadura']
  #            insert into usuarios (matricula, nome, tipoUsuario, nivelGerencia) values ("  009876   ","   len","             ","               ")
  sql =       ("insert into salas (codigo, nome, local, fechadura) values (%s,%s,%s,%s)")
  d = (codigo, nome, local, fechadura)
  logger.debug(sql % d)

  try:
    cur.execute(sql, d)
    mysql.connection.commit()
  except Exception as e: 
    cur.close()
    logger.warning(str(e))
    return {"status": str(e)}
    # return s

  cur.close()
  
  return {"status":"ok"}

#modifica ou deleta uma sala do banco
@app.route('/sala/<sala_id>', methods = ['PUT', 'DELETE'])
def modifica_salas(sala_id):

  if request.method == 'PUT':
    data = request.json
    
    try:
      cur = mysql.connection.cursor() 
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}
    
    sql  = "UPDATE salas SET "
    sql += "nome='" + data["nome"] +"', codigo='"+data["codigo"]+"'"
    sql += ", fechadura='"+ data["fechadura"] +"', local='"+ data["local"] +"'"
    sql += " WHERE id='"+sala_id+"'"

    logger.debug(sql)

    cur.execute(sql)
    mysql.connection.commit()

    return {"status":"ok"}

  if request.method == 'DELETE':
    try:
      cur = mysql.connection.cursor() 
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}   
    sql = ("DELETE FROM salas WHERE id="+sala_id)

    cur.execute(sql)
    mysql.connection.commit()

    return {"resultado":{"status":"ok"}}

#retorna todas as salas que um determinado usuário está com acesso
@app.route('/salasAutorizadas/<user_id>', methods = ['POST'])
def getSalasAutorizadas(user_id):

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  sql = "SELECT  s.nome, s.codigo FROM usuarios u "
  sql += "JOIN autorizacao aut ON u.id = aut.id_usuario "
  sql += "JOIN salas s ON aut.id_sala = s.id "
  sql += "WHERE u.matricula = "+ user_id


  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]

  return {"status":"ok", "data":data}

# Dá autorização a um usuário para entrar em determinada sala
@app.route('/autorizarUsuario/<user_id>', methods = ['PUT', 'DELETE'])
def autorizar_usuario(user_id):
  try:
    cur = mysql.connection.cursor()
  except Exception as e: 
    logger.warning(str(e))
    return {"status": str(e)}

  if request.method == 'PUT':
    cod_salas      = request.json

    sql = "select id from salas where (codigo='"+cod_salas[0]+"')"
    for cod_sala in cod_salas:
      if cod_sala != cod_salas[0]:
        sql += "or (codigo='"+cod_sala+"')"

    try:
      cur.execute(sql)
    except Exception as e:
      cur.close()
      return {"status": str(e)}

    columns = [column[0] for column in cur.description]
    salas = [dict(zip(columns, row)) for row in cur.fetchall()]
    # fechadura   = data["fechadura"]
    # data = cur.fetchall()
    

    for i in salas:
      logger.debug(i["id"])

        
    sql = "select id from usuarios where matricula='"+user_id+"'"
    try:
      cur.execute(sql)
    except Exception as e:
      cur.close()
      return {"status": str(e)}

    columns = [column[0] for column in cur.description]
    data = [dict(zip(columns, row)) for row in cur.fetchall()]
    # chave = data[0]["chave"]
    id_usuario = data[0]["id"]

    # print(chave)
    # print(id_usuario)

    # if chave == None:
    #   print("chave null")
    #   return {"status": "sem chave"}

    sql =  "insert into autorizacao (id_usuario, id_sala)" 
    sql += " values ('"+str(id_usuario)+"','"+str(salas[0]["id"])+"')"
    
    for sala in salas:
      if sala["id"] != salas[0]["id"]:
        sql += ",('"+str(id_usuario)+"','"+str(sala["id"])+"')"

    logger.debug(sql)

    try:
      cur.execute(sql)
      mysql.connection.commit()
    except Exception as e: 
      cur.close()
      logger.warning(str(e))
      return {"status": str(e)}
      # return s

    cur.close()
    
    return {"status":"ok"}
  
  if request.method == 'DELETE':
    sql = "delete autorizacao from autorizacao "
    sql += "join usuarios on usuarios.id = autorizacao.id_usuario where "
    sql += "matricula='"+user_id+"'"

    try:
      cur.execute(sql)
      mysql.connection.commit()
    except Exception as e:
      cur.close()
      logger.warning(str(e))
      return {"status": str(e)}

    cur.close()
    return {"status":"ok"}

# Dá autorização a uma lista de usuários para entrar em uma determinada sala
@app.route('/autorizarUsuariosPorSala/<cod_sala>', methods = ['PUT', 'DELETE'])
def autorizarUsuariosPorSala(cod_sala):
  logger.debug(request.json)

  try:
    cur = mysql.connection.cursor()
  except Exception as e: 
    logger.warning(str(e))
    return {"status": str(e)}
  
  usuarios = request.json["usuarios"]
  if request.method == 'PUT':
    dataInicio = request.json["dataInicio"]
    dataFim = request.json["dataFim"]
    horarioInicio = request.json["horarioInicio"]
    horarioFim = request.json["horarioFim"]

    dados_para_upsert = [
    {"id_usuario": 1, "id_sala": 1},
    {"id_usuario": 1, "id_sala": 4},
    {"id_usuario": 1, "id_sala": 5}
    ]

    # INSERT INTO autorizacao (id_usuario, id_sala, data_limite, data_inicio, horario_inicio, horario_fim)
    # VALUES (%s, %s, %s, %s, %s, %s)
    # sql = """
    # INSERT INTO autorizacao (id_usuario, id_sala)
    # VALUES (%s, %s)
    # ON DUPLICATE KEY UPDATE preco = VALUES(preco)
    # """
    for usuario in usuarios:
      matricula = usuario["matricula"]
      sql = "SELECT  aut.id FROM usuarios u "
      sql += "JOIN autorizacao aut ON u.id = aut.id_usuario "
      sql += "JOIN salas s ON aut.id_sala = s.id "
      sql += "WHERE u.matricula = '"+matricula+"' "
      sql += "and s.codigo='"+cod_sala+"'"

      try:
        cur.execute(sql)
        mysql.connection.commit()
      except Exception as e:
        cur.close()
        logger.warning(str(e))
        return {"status": str(e)}
      
      numResults = cur.rowcount

      if numResults > 0 :
        columns = [column[0] for column in cur.description]
        data = [dict(zip(columns, row)) for row in cur.fetchall()]
        logger.debug(data)
 
        id = data[0]["id"]
        logger.debug(data)
        logger.debug(id)
        if dataFim is None :
          sql = "update autorizacao set data_inicio= '"+dataInicio+"', data_limite= NULL, "
          sql += "horario_inicio= '"+horarioInicio+"', horario_fim= '"+horarioFim+"' "
          sql += "where id='"+str(id)+"'"
        else :
          sql = "update autorizacao set data_limite= '"+dataFim+"',  data_inicio= '"+dataInicio+"', "
          sql += "horario_inicio= '"+horarioInicio+"', horario_fim= '"+horarioFim+"' "
          sql += "where id='"+str(id)+"'"
        try:
          cur.execute(sql)
          mysql.connection.commit()
        except Exception as e:
          cur.close()
          logger.warning(str(e))
          return {"status": str(e)}
      else :
        logger.debug("vai inserir agora")
        logger.debug(usuario)
        sql = "insert into autorizacao (id_sala, id_usuario) "
        sql += "select salas.id, usuarios.id from salas, usuarios "
        sql += "where salas.codigo='"+cod_sala+"' and usuarios.matricula='"+matricula+"'"
        logger.debug(sql)
        try:
          cur.execute(sql)
          mysql.connection.commit()
        except Exception as e:
          cur.close()
          logger.warning(str(e))
          return {"status": str(e)}
        
        sql = "select aut.id "
        logger.debug(numResults)
        
        sql = "SELECT  aut.id FROM usuarios u "
        sql += "JOIN autorizacao aut ON u.id = aut.id_usuario "
        sql += "JOIN salas s ON aut.id_sala = s.id "
        sql += "WHERE u.matricula = '"+matricula+"' "
        sql += "and s.codigo='"+cod_sala+"'"

        try:
          cur.execute(sql)
          mysql.connection.commit()
        except Exception as e:
          cur.close()
          logger.warning(str(e))
          return {"status": str(e)}
        
        columns = [column[0] for column in cur.description]
        data = [dict(zip(columns, row)) for row in cur.fetchall()]
        id = data[0]["id"]
        
        if dataFim is None :
          sql = "update autorizacao set data_inicio= '"+dataInicio+"', "
          sql += "horario_inicio= '"+horarioInicio+"', horario_fim= '"+horarioFim+"' "
          sql += "where id='"+str(id)+"'"
        else :
          sql = "update autorizacao set data_limite= '"+dataFim+"',  data_inicio= '"+dataInicio+"', "
          sql += "horario_inicio= '"+horarioInicio+"', horario_fim= '"+horarioFim+"' "
          sql += "where id='"+str(id)+"'"
        
        try:
          cur.execute(sql)
          mysql.connection.commit()
        except Exception as e:
          cur.close()
          logger.warning(str(e))
          return {"status": str(e)}

  
    return {"status":"ok"}
  
  if request.method == 'DELETE':
    for usuario in usuarios:
      matricula = usuario["matricula"]
      sql = "DELETE autorizacao from autorizacao "
      sql += "join usuarios on usuarios.id = autorizacao.id_usuario "
      sql += "join salas on salas.id = autorizacao.id_sala  "
      sql += "where salas.codigo='"+cod_sala+"' and usuarios.matricula='"+matricula+"'"
      # delete autorizacao from autorizacao aut JOIN usuarios u ON u.id = aut.id_usuario JOIN salas s ON aut.id_sala = s.id where u.matricula='' and s.codigo=''
      # DELETE autorizacao from autorizacao join salas on salas.id = autorizacao.id_sala join usuarios on usuarios.id = autorizacao.id_usuario where salas.codigo='a208' and usuarios.matricula='1934598';

      try:
        cur.execute(sql)
        mysql.connection.commit()
      except Exception as e:
        cur.close()
        logger.warning(str(e))
        return {"status": str(e)}

    cur.close()
    return {"status":"ok"}

# retorna o número de acesso realizados hoje
@app.route('/acessosHoje', methods = ['GET'])
def acessos_hoje():
  current_dateTime = datetime.now()
  today = datetime.now().date()

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  try:
    cur.execute("select * from acessos where DATE(timestamp) = '"+str(today)+"'" )
  except Exception as e:
    cur.close()
    logger.warning(e)
    return {"status":str(e)}

  numResults = cur.rowcount
  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]

  cur.close()

  return {'numAcessos': numResults, 'acessos': data}

# retorna o número de acessos realizados em uma data específica
@app.route('/acessosData', methods = ['PUT'])
def acessos_data():
  data_inicial = request.json["data_inicial"]
  data_final = request.json["data_final"]

  #sql = "select * from acessos where DATE(timestamp) = '"+str(today)+"'"
  sql = "select * from acessos where DATE(timestamp) <= '"+data_final+"'"
  sql += " and DATE(timestamp) >= '"+data_inicial+"'"

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  try:
    cur.execute( sql )
  except Exception as e:
    cur.close()
    logger.warning(str(e))
    return {"status": str(e)}

  numResults = cur.rowcount
  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]
  

  return {"status":"ok", "numResults": numResults, "Dados": data}

# retorna os dados de acessos realizados por um usuário em uma data específica
@app.route('/dataAcessosPorDataPorUsuario/<user_id>', methods = ['POST'])
def getDatasAcessosPorUsuarioPorData(user_id):
  data_inicial = request.json["data_inicial"]
  data_final = request.json["data_final"] 

  # logger.debug("Data final")
  # logger.debug(data_final)
  # logger.debug("Data inicial")
  # logger.debug(data_inicial)

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}
  
  sql = "SELECT a.timestamp, a.autorizado, s.codigo, s.nome FROM usuarios u "
  sql += "JOIN acessos a ON u.matricula = a.usuario "
  sql += "JOIN salas s ON a.sala = s.id "
  sql += "WHERE u.matricula = '" + user_id + "'"
  sql += " and DATE(a.timestamp) <= '"+data_final+"'"
  sql += " and DATE(a.timestamp) >= '"+data_inicial+"'"
  sql += " order by a.timestamp"

  # logger.debug("SQL")
  # logger.debug(sql)

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}
  
  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]

  # logger.debug("Resultado")
  # logger.debug(data)

  return {"status":"ok", "data": data}

# retornar o número de acessos realizados por um determinado usuário
@app.route('/acessosPorUsuario/<user_id>', methods = ['POST'])
def getAcessosPorUsuario(user_id):

  data_inicial = request.json["data_inicial"]
  data_final = request.json["data_final"] 

  # logger.debug("Data final")
  # logger.debug(data_final)
  # logger.debug("Data inicial")
  # logger.debug(data_inicial)

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  # sql = "select * from acessos where DATE(timestamp) <= '"+data_final+"'"
  # sql += " and DATE(timestamp) >= '"+data_inicial+"'"

  sql = "SELECT  a.usuario, s.codigo FROM usuarios u "
  sql += "JOIN acessos a ON u.matricula = a.usuario "
  sql += "JOIN salas s ON a.sala = s.id "
  sql += "WHERE u.matricula = '" + user_id + "'"
  sql += " and DATE(a.timestamp) <= '"+data_final+"'"
  sql += " and DATE(a.timestamp) >= '"+data_inicial+"'"

  # logger.debug("SQL")
  # logger.debug(sql)

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  
  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]

  list = {}

  for acesso in data:
    if acesso["codigo"] not in list:
      list[acesso["codigo"]] = 1
    else:
      temp = list[acesso["codigo"]]
      temp = temp + 1
      list[acesso["codigo"]] = temp
  
  return {"status":"ok", "data": list}

# retorna os usuarios que acessaram uma sala em uma data específica
@app.route('/getAcessosPorSala/<sala_codigo>', methods = ['POST'])
def getAcessosPorSala(sala_codigo):
  data_inicial = request.json["data_inicial"]
  data_final = request.json["data_final"] 

  # logger.debug("Data final")
  # logger.debug(data_final)
  # logger.debug("Data inicial")
  # logger.debug(data_inicial)

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  # sql = "select * from acessos where DATE(timestamp) <= '"+data_final+"'"
  # sql += " and DATE(timestamp) >= '"+data_inicial+"'"

  sql = "SELECT  u.nome, u.matricula, a.timestamp, a.autorizado FROM usuarios u "
  sql += "JOIN acessos a ON u.matricula = a.usuario "
  sql += "JOIN salas s ON a.sala = s.id "
  sql += "WHERE s.codigo = '" + sala_codigo + "'"
  sql += " and DATE(a.timestamp) <= '"+data_final+"'"
  sql += " and DATE(a.timestamp) >= '"+data_inicial+"'"
  sql += " order by a.timestamp"

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  
  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]
  
  # list = {}

  # for acesso in data:
  #   if acesso["matricula"] not in list:
  #     list[acesso["matricula"]] = 1
  #   else:
  #     temp = list[acesso["matricula"]]
  #     temp = temp + 1
  #     list[acesso["matricula"]] = temp
  
  return {"status":"ok", "data": data}

# retorna os usuarios que acessaram cada uma das salas em uma data específica
@app.route('/getTodosAcessosPorSala', methods = ['POST'])
def getTodosAcessosPorSala():
  data_inicial = request.json["data_inicial"]
  data_final = request.json["data_final"] 

  # logger.debug("Data final")
  # logger.debug(data_final)
  # logger.debug("Data inicial")
  # logger.debug(data_inicial)

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  # sql = "select * from acessos where DATE(timestamp) <= '"+data_final+"'"
  # sql += " and DATE(timestamp) >= '"+data_inicial+"'"

  sql = "SELECT  s.codigo, u.nome, u.matricula, a.timestamp, a.autorizado FROM usuarios u "
  sql += "JOIN acessos a ON u.matricula = a.usuario "
  sql += "JOIN salas s ON a.sala = s.id "
  sql += "WHERE DATE(a.timestamp) <= '"+data_final+"'"
  sql += " and DATE(a.timestamp) >= '"+data_inicial+"'"
  sql += " order by s.codigo, a.timestamp"

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  
  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]
  
  list = {}

  for acesso in data:
    if acesso["codigo"] not in list:
      list[acesso["codigo"]] = 1
    else:
      temp = list[acesso["codigo"]]
      temp = temp + 1
      list[acesso["codigo"]] = temp
  
  return {"status":"ok", "data": data, "numAccess": list}

@app.route('/getUsuariosAtivos', methods = ['GET'])
def getNumeroUsuariosAtivos():

  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  sql = "SELECT * FROM usuarios where ativo=1"

  try:
    cur.execute(sql)
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}
  
  
  columns = [column[0] for column in cur.description]
  users = [dict(zip(columns, row)) for row in cur.fetchall()]

  return {"status":"ok", "users":users}

# função para realizar login no sistema
@app.route('/login', methods = ['POST'])
def login():
  api_url = "https://suap.ifrn.edu.br/api/"

  try:
    data = request.json
    response = requests.post(api_url + "v2/autenticacao/token/", json=data)
  except Exception as e:
    logger.warning(str(e))
    return {"status": "falha login", "erro": str(e)}
  
  if response.status_code == 200:
    global token_refresh
    token_refresh = response.json().get("refresh")
    token = response.json().get("access")

    headers = {
        "Authorization": f'Bearer {token}'
    }
    try:
      response_meus_dados = requests.get(api_url + "v2/minhas-informacoes/meus-dados/", headers=headers)
    except Exception as e:
      logger.warning(str(e))
      return {"status": str(e)}

    if response_meus_dados.status_code == 200:
      logger.debug("Informações do Aluno:")
      # logger.debug(response_meus_dados.json())
      logger.debug("")
      logger.debug(response_meus_dados.json()["matricula"])
      # logger.debug(response_meus_dados.json()["tipo_vinculo"])
      vinculo = response_meus_dados.json()["vinculo"]
      logger.debug(vinculo["campus"])
      # logger.debug(token)

      matricula = response_meus_dados.json()["matricula"]
      tipo_vinculo = response_meus_dados.json()["tipo_vinculo"]
      campus = vinculo["campus"]
      url_foto = response_meus_dados.json()["url_foto_75x100"]
      nome_usual = response_meus_dados.json()["nome_usual"]
      tipo_usuario = ""

      sql = "SELECT * FROM usuarios WHERE matricula = '"+ matricula +"'"

      try:
        cur = mysql.connection.cursor()
      except Exception as e:
        logger.warning("falha de acesso ao banco: "+str(e))
        return {"status":str(e)}

      try:
        cur.execute(sql)
      except Exception as e:
        cur.close()
        logger.warning(str(e))
        return {"status":str(e)}
      
      numResults = cur.rowcount

      tipo_sql = ""
      if response_meus_dados.json()["tipo_vinculo"] == "Servidor" :
        tipo_sql = vinculo["categoria"]
      else:
        tipo_sql = "aluno"

      tipo_usuario = tipo_sql

      if numResults == 0:
        nome_sql = nome_usual
        matr_sql = matricula
        # matr_sql = "12345"
        nivel_sql = "usuário"

        # logger.debug(tipo_usuario)
        sql =       ("insert into usuarios (matricula, nome, tipoUsuario, nivelGerencia) values (%s,%s,%s,%s)")
        d = (matr_sql, nome_sql, tipo_sql, nivel_sql)
        # logger.debug(sql % d)

        try:
          cur.execute(sql, d)
          mysql.connection.commit()
        except Exception as e:
          cur.close()
          logger.warning("falha de acesso ao banco: "+str(e))
          return {"status":str(e)}

      sql = "SELECT nivelGerencia FROM usuarios WHERE matricula = '"+ matricula +"'"      
      try:
        cur.execute(sql)
        nivel_gerencia = cur.fetchall()[0][0]
      except Exception as e:
        cur.close()
        logger.warning("falha de acesso ao banco: "+str(e))
        return {"status":str(e)}
      
      # logger.debug( nivel_gerencia )
      cur.close()

      user_roles = {"nivelGerencia": nivel_gerencia, "tipoUsuario": tipo_usuario}
      access_token = create_access_token(identity=matricula, additional_claims={"roles": user_roles})
      # access_token = create_access_token(identity=user_id, additional_claims={"roles": user_roles})
      
      return {"status":"ok", "data": {"token": token, "token_local": access_token, "matricula": matricula, "nome_usual": nome_usual, "campus": campus, "tipoUsuario": tipo_usuario, "foto": url_foto, "nivelGerencia": nivel_gerencia }}
    else:
        logger.warning(f"Erro ao obter informações. Código de status: {response_meus_dados.status_code}")
        return{"status":"erro"}
  else:
    logger.warning("Erro na autenticação no suap. Verifique seu usuário e senha.")
    return{"status": "falha_login", "erro" : "falha de comunicação com SUAP"}

  return {"status":"ok", "token": token}
