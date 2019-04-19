SENECA_SC_PATH = 'seneca.contracts'

DB_TYPE = 'redis'

DB_URL = 'localhost'
DB_PORT = 6379
MASTER_DB = 0
DB_OFFSET = 1
CODE_OBJ_MAX_CACHE = 64

DB_DELIMITER = ':'

# Number of available db's SenecaClients have available to get ahead on the next sub block while other sb's are
# awaiting a merge confirmation
NUM_CACHES = 2

# Number of sb's to queue up if we run out of caches
MAX_SB_QUEUE_SIZE = 8

# Resource limits
MEMORY_LIMIT = 32768 # 32kb
RECURSION_LIMIT = 1024

DELIMITER = ':'
CODE_KEY = '__code__'
TYPE_KEY = '__type__'
AUTHOR_KEY = '__author__'
INDEX_SEPARATOR = '.'


DECIMAL_PRECISION = 64

PRIVATE_METHOD_PREFIX = '__'
EXPORT_DECORATOR_STRING = 'seneca_export'
INIT_DECORATOR_STRING = 'seneca_construct'
INIT_FUNC_NAME = '{}__'.format(PRIVATE_METHOD_PREFIX)
VALID_DECORATORS = {EXPORT_DECORATOR_STRING, INIT_DECORATOR_STRING}

ORM_CLASS_NAMES = {'Variable', 'Hash', 'ForeignVariable', 'ForeignHash'}