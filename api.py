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

mysql = MySQL(app)

# Usado unica e exclusivamente para testes
@app.route('/time')
def get_current_time():
  # logger.debug("teste")
  return {'time': time.time()}

# Usado para retornar lista de usuários
@app.route('/usuarios', methods = ['GET', 'POST'])
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
def add_data():
  try:
    cur = mysql.connection.cursor()
  except Exception as e:
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  logger.debug (request.json)
  nome          = request.json["nome"]
  matricula     = request.json["matricula"]
  tipoUsuario   = request.json['tipoUsuario']
  nivelGerencia = request.json['nivelGerencia']
  #            insert into usuarios (matricula, nome, tipoUsuario, nivelGerencia) values ("  009876   ","   len","             ","               ")
  sql =       ("insert into usuarios (matricula, nome, tipoUsuario, nivelGerencia) values (%s,%s,%s,%s)")
  d = (matricula, nome, tipoUsuario, nivelGerencia)
  logger.debug(sql % d)

  try:
    cur.execute(sql, d)
    mysql.connection.commit()
  except Exception as e:
    cur.close()
    logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}

  cur.close()
  
  return {"status":"ok"}

# Usado para adicionar uma nova sala ao banco
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

# Usado para retornar,modificar dados de um usuário ou deletar um usuário
@app.route('/usuario/<user_id>', methods = ['GET', 'PUT', 'DELETE'])
def data(user_id):

  if request.method == 'GET':
    try:
      cur = mysql.connection.cursor()
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}

    try:
      cur.execute("SELECT * FROM usuarios WHERE id="+user_id)
    except Exception as e:
      cur.close()
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}
    columns = [column[0] for column in cur.description]
    data = [dict(zip(columns, row)) for row in cur.fetchall()]

    logger.debug(str(data))

    return data
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
@app.route('/sala/<user_id>', methods = ['PUT', 'DELETE'])
def delete_data(user_id):

  if request.method == 'DELETE':
    try:
      cur = mysql.connection.cursor() 
    except Exception as e:
      logger.warning("falha de acesso ao banco: "+str(e))
      return {"status":str(e)}   
    sql = ("DELETE FROM salas WHERE id="+user_id)

    cur.execute(sql)
    mysql.connection.commit()

    return {"resultado":{"status":"ok"}}

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
      logger.debug(response_meus_dados.json())
      logger.debug("")
      logger.debug(response_meus_dados.json()["matricula"])
      logger.debug(response_meus_dados.json()["tipo_vinculo"])
      vinculo = response_meus_dados.json()["vinculo"]
      logger.debug(vinculo["campus"])
      logger.debug(token)

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

        logger.debug(tipo_usuario)
        sql =       ("insert into usuarios (matricula, nome, tipoUsuario, nivelGerencia) values (%s,%s,%s,%s)")
        d = (matr_sql, nome_sql, tipo_sql, nivel_sql)
        logger.debug(sql % d)

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
      
      logger.debug( nivel_gerencia )
      cur.close()

      return {"status":"ok", "data": {"token": token, "matricula": matricula, "nome_usual": nome_usual, "campus": campus, "tipoUsuario": tipo_usuario, "foto": url_foto, "nivelGerencia": nivel_gerencia }}
    else:
        logger.warning(f"Erro ao obter informações. Código de status: {response_meus_dados.status_code}")
        return{"status":"erro"}
  else:
    logger.warning("Erro na autenticação no suap. Verifique seu usuário e senha.")
    return{"status": "falha_login", "erro" : "falha de comunicação com SUAP"}

  return {"status":"ok", "token": token}
