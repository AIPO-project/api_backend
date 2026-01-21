# from flask_mysqldb import MySQL

# _sql=""
_mysql=""
_logger=""

def init(my_sql, logger):
  global _mysql
  global _logger
  _logger = logger
  _mysql = my_sql

def set_sql(sql):
  _sql = sql

def run_select(sql):
  try:
    cur = _mysql.connection.cursor()
  except Exception as e:
    _logger.warning("falha de acesso ao banco: "+str(e))
    return {"status":str(e)}
  
  try:
    cur.execute( sql )
  except Exception as e:
    cur.close()
    _logger.warning(str(e))
    return {"status": str(e)}
  
  # numResults = cur.rowcount
  columns = [column[0] for column in cur.description]
  data = [dict(zip(columns, row)) for row in cur.fetchall()]

  cur.close()

  return data