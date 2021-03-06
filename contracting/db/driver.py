import abc
import copy
import dbm

# we can't include pylevel in production since its not installed on the docker images and will
# result in an interpret time error
from redis import Redis
from redis.connection import Connection
from .. import config
from ..exceptions import DatabaseDriverNotFound
from ..db.encoder import encode, decode

from ..logger import get_logger
from ..execution.runtime import rt

from .. import config

from collections import deque, defaultdict
import marshal

class AbstractDatabaseDriver:
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __getstate__(self):
        """Remove unpicklable objects (i.e. conn)"""
        return

    @abc.abstractmethod
    def __setstate__(self, state):
        """Re-add unpicklable objects (i.e. conn)"""
        return

    @abc.abstractmethod
    def get(self, key):
        """Get the specified _key from the database"""
        return

    @abc.abstractmethod
    def set(self, key, value):
        """Set the specified _key in the database"""
        return

    @abc.abstractmethod
    def delete(self, key):
        """Delete the specified _key from the Database"""
        return

    @abc.abstractmethod
    def flush(self, db):
        """Flush the selected database of all entries"""
        return

    @abc.abstractmethod
    def iter(self, prefix):
        return

    @abc.abstractmethod
    def keys(self):
        """Do a scan on the connection for all available keys"""
        return

    def exists(self, key):
        """Check whether a given _key exists before attempting to query it"""
        if self.get(key) is not None:
            return True
        return False

'''
import plyvel
class LevelDBDriver(AbstractDatabaseDriver):
    def __init__(self, db=config.MASTER_DB, **kwargs):
        self.db_name = 'state.db'
        if db != config.MASTER_DB:
            self.db_name = 'cache_{}.db'.format(db)
        self.conn = plyvel.DB(self.db_name, create_if_missing=True, error_if_exists=False)

    def get(self, _key):
        try:
            _key = _key.encode()
        except AttributeError:
            pass

        return self.conn.get(_key)

    def set(self, _key, value):
        try:
            _key = _key.encode()
        except AttributeError:
            pass

        try:
            value = value.encode()
        except AttributeError:
            pass
        self.conn.put(_key, value)

    def delete(self, _key):
        try:
            _key = _key.encode()
        except AttributeError:
            pass

        self.conn.delete(_key)

    def iter(self, prefix):
        try:
            prefix = prefix.encode()
        except AttributeError:
            pass
        it = self.conn.iterator(prefix=prefix)
        return [k[0] for k in it]

    def keys(self):
        return self.iter(prefix=b'')

    def flush(self, db=None):
        for k in self.keys():
            self.delete(k)

    def incrby(self, _key, amount=1):
        """Increment a numeric _key by one"""
        try:
            _key = _key.encode()
        except:
            pass

        k = self.conn.get(_key)

        if k is None:
            k = 0
        k = int(k) + amount

        self.conn.put(_key, '{}'.format(k).encode())

        return k
'''

# The theoretically fastest _driver. It's a dictionary.
class DictDriver(AbstractDatabaseDriver):
    def __init__(self, **kwargs):
        self.conn = {}

    def get(self, key):
        return self.conn.get(key)

    def set(self, key, value):
        self.conn[key] = value

    def delete(self, key):
        del self.conn[key]

    def iter(self, prefix):
        keys = []
        for k, v in self.conn.items():
            if k.startswith(prefix):
                keys.append(k)
        return keys

    def keys(self):
        return self.conn.keys()

    def flush(self, db=None):
        del self.conn
        self.conn = {}

    def incrby(self, key, amount=1):
        """Increment a numeric _key by one"""
        k = self.get(key)

        if k is None:
            k = 0
        k = int(k) + amount
        self.set(key, k)

        return k

import atexit
class DBMDriver(AbstractDatabaseDriver):
    def __init__(self, dir='./', db=0, **kwargs):
        self.filename = '{}{}'.format(dir, db)

        # Make sure the DB exists and close it after writing
        self.db = dbm.open(self.filename, 'c')
        atexit.register(self.close)

    def close(self):
        self.db.close()

    def get(self, key):
        #with dbm.open(self.filename, 'r') as db:
        try:
            return self.db[key]
        except:
            return None

    def set(self, key, value):
        #with dbm.open(self.filename, 'w') as db:
        self.db[key] = value

    def delete(self, key):
        #with dbm.open(self.filename, 'w') as db:
        del self.db[key]

    def iter(self, prefix):
        try:
            prefix = prefix.encode()
        except:
            pass

        keys = []

        for k in self.keys():
            try:
                k = k.encode()
            except:
                pass
            if k.startswith(prefix):
                keys.append(k)
        return keys

    def keys(self):
        all_keys = []

        #with dbm.open(self.filename, 'r') as db:
        all_keys.extend(self.db.keys())
        return all_keys

    def flush(self, db=None):
        for k in self.keys():
            self.delete(k)

    def incrby(self, key, amount=1):
        k = self.get(key)

        if k is None:
            k = 0
        k = int(k) + amount
        self.set(key, k)

        return k


class RedisConnectionDriver(AbstractDatabaseDriver):
    def __init__(self, host=config.DB_URL, port=config.DB_PORT, db=config.MASTER_DB):
        self.host = host
        self.db = db
        self.port = port
        self.conn = None
        self._setup_conn()

    def _setup_conn(self):
        self.conn = Connection(self.host, self.port, self.db)

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['conn']
        return state

    def __setstate__(self, state):
        for k,v in state.items():
            setattr(self, k, v)
        self._setup_conn()

    def get(self, key):
        self.conn.send_command('GET', key)
        resp = self.conn.read_response()
        #print("GET {} RESPONSE: {}".format(_key,
        return resp

    def set(self, key, value):
        self.conn.send_command('SET', key, value)
        resp = self.conn.read_response()
        #print("SET {} RESPONSE: {}".format(_key, resp))

    def delete(self, key):
        self.conn.send_command('DEL', key)
        self.conn.read_response()

    def iter(self, prefix):
        self.conn.send_command('KEYS', prefix+'*')
        return self.conn.read_response()

    def keys(self):
        return self.iter(prefix='')

    def flush(self, db=None):
        self.conn.send_command('FLUSHDB')
        self.conn.read_response()

    def incrby(self, key, amount=1):
        """Increment a numeric _key by one"""
        k = self.conn.send_command('GET', key)

        if k is None:
            k = 0
        k = int(k) + amount
        self.conn.send_command('SET', key, k)

        return k


class RedisDriver(AbstractDatabaseDriver):
    def __init__(self, host=config.DB_URL, port=config.DB_PORT, db=config.MASTER_DB):
        self.host = host
        self.port = port
        self.db = db
        self.conn = None
        self.connection_pool = None
        self._setup_conn()

    def _setup_conn(self):
        self.conn = Redis(host=self.host, port=self.port, db=self.db)
        self.connection_pool = self.conn.connection_pool

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['conn']
        del state['connection_pool']
        return state

    def __setstate__(self, state):
        for k, v in state.items():
            setattr(self, k, v)
        self._setup_conn()

    def get(self, key):
        val = self.conn.get(key)

        if val is not None and rt.tracer.is_started():
            cost = len(key) + len(val)
            cost *= config.READ_COST_PER_BYTE
            rt.tracer.add_cost(cost)

        return val

    def set(self, key, value):

        if rt.tracer.is_started():
            cost = len(key) + len(value)
            cost *= config.READ_COST_PER_BYTE
            rt.tracer.add_cost(cost)

        self.conn.set(key, value)

    def delete(self, key):
        self.conn.delete(key)

    def iter(self, prefix):
        return list(self.conn.scan_iter(match=prefix+'*'))

    def keys(self):
        return self.conn.keys(pattern='*')

    def flush(self, db=None):
        self.conn.flushdb()

    def incrby(self, key, amount=1):
        """Increment a numeric _key by one"""
        k = self.conn.get(key)

        if k is None:
            k = 0
        k = int(k) + amount
        self.conn.set(key, k)

        return k

# Defined at the bottom since needs to be instantiated
# after the classes have been defined. Allows us to
# parameterize the type of database _driver required
# from the top level instead of having to manually change
# a bunch of code to get to it.
DATABASE_DRIVER_MAPS = {
    'redis': RedisConnectionDriver
}


def get_database_driver():
    cls = DATABASE_DRIVER_MAPS.get(config.DB_TYPE)
    if cls is None:
        raise DatabaseDriverNotFound(
            driver=config.DB_TYPE,
            known_drivers=DATABASE_DRIVER_MAPS.keys())
    return cls


DatabaseDriver = get_database_driver()
#DatabaseDriver = LevelDBDriver
DatabaseDriver = RedisDriver


class CacheDriver(DatabaseDriver):
    def __init__(self, host=config.DB_URL, port=config.DB_PORT, db=0,):
        super().__init__(host=host, port=port, db=db)
        self.log = get_logger("CacheDriver")
        self.modified_keys = None
        self.contract_modifications = None
        self.original_values = None
        self.reset_cache()

    def reset_cache(self, modified_keys=None, contract_modifications=None, original_values=None):
        # Modified keys is a dictionary of deques representing the contracts that have modified
        # that _key
        if modified_keys:
            self.modified_keys = copy.deepcopy(modified_keys)
        else:
            self.modified_keys = defaultdict(deque)
        # Contract modififications is a list of dicts containing the keys updated by a contract
        # and their final value
        if contract_modifications:
            self.contract_modifications = copy.deepcopy(contract_modifications)
        else:
            self.contract_modifications = []
        # Original values is a dictionary of keys representing the original value fetched from
        # the DB
        if original_values:
            self.original_values = copy.deepcopy(original_values)
        else:
            self.original_values = {}

        # If we do not have any contract modifications, add a new one
        if len(self.contract_modifications) == 0:
            self.new_tx()

    def get(self, key):
        key_location = self.modified_keys.get(key)
        if key_location is None:
            value = super().get(key)
            self.original_values[key] = value
        else:
            value = self.contract_modifications[key_location[-1]][key]
        return value

    def get_direct(self, key):
        return super().get(key)

    def set(self, key, value):
        self.contract_modifications[-1].update({key: value})
        # TODO: May have multiple instances of contract_idx if multiple sets on same _key
        self.modified_keys[key].append(len(self.contract_modifications) - 1)

    def delete(self, key):
        self.set(key, None) # Indirection is going on here where None gets encoded into JSONs none

    def set_direct(self, key, value):
        super().set(key, value)

    def revert(self, idx=0):
        if idx == 0:
            self.reset_cache()
        else:
            for key, i in self.modified_keys.items():
                while len(i) >= 1:
                    if i[-1] >= idx:
                        i.pop()
                    else:
                        break
                if len(i) == 0:
                    i = None
                self.modified_keys[key] = i

            self.contract_modifications = self.contract_modifications[:idx + 1]
            # self.contract_modifications[idx].clear()
            # for mod_dict in self.contract_modifications[:idx + 1]:

    def commit(self):
        for key, idx in self.modified_keys.items():
            value = self.contract_modifications[idx[-1]][key]
            if value == 'null': # This shit is null because that is the JSON representation and the data is being encoded in the contract driver
                super().delete(key)
            else:
                super().set(key, value)

        self.reset_cache()
    #

    def iter(self, prefix):
        keys = set(super().iter(prefix=prefix))
        for k in self.modified_keys.keys():
            if k not in keys and k.startswith(prefix):
                keys.add(k)
        return list(keys)

    def new_tx(self):
        self.contract_modifications.append(dict())


class ContractDriver(CacheDriver):
    def __init__(self, host=config.DB_URL, port=config.DB_PORT, delimiter=config.INDEX_SEPARATOR, db=0,
                 code_key=config.CODE_KEY, type_key=config.TYPE_KEY, author_key=config.AUTHOR_KEY):
        super().__init__(host=host, port=port, db=db)

        self.delimiter = delimiter

        self.code_key = code_key
        self.type_key = type_key
        self.author_key = author_key

        # Tests if access to the DB is available
        #self.conn.ping()

    def get(self, key):
        value = super().get(key)
        return decode(value)

    def set(self, key, value):
        v = encode(value)
        super().set(key, v)

    def values(self, prefix):
        keys = super().iter(prefix=prefix)
        values = []
        for key in keys:
            value = self.get(key)
            values.append(value)
        return values

    def items(self, prefix):
        keys = self.iter(prefix=prefix)
        kvs = []
        for key in keys:
            value = self.get(key)
            kvs.append((key, value))
        return kvs

    def make_key(self, key, field):
        return '{}{}{}'.format(key, self.delimiter, field)

    def hget(self, key, field):
        return self.get(
            self.make_key(key, field)
        )

    def hset(self, key, field, value):
        return self.set(
            self.make_key(key, field),
            value=value
        )

    def get_contract(self, name):
        return self.hget(name, self.code_key)

    def set_contract(self, name, code, author='sys', _type='user', overwrite=False):
        if not overwrite or self.is_contract(name):
            self.hset(name, self.code_key, code)
            self.hset(name, self.author_key, author)
            self.hset(name, self.type_key, _type)

            code_obj = compile(code, '', 'exec')
            code_blob = marshal.dumps(code_obj)
            self.hset(name, '__compiled__', code_blob)

    def get_compiled(self, name):
        return self.hget(name, '__compiled__')

    def delete_contract(self, name):
        for k in self.iter(prefix=name):
            self.delete(k)

    def is_contract(self, name):
        return self.exists(
            self.make_key(name, self.code_key)
        )

    def keys(self):
        return [k.decode() for k in super().keys()]

    def get_contract_keys(self, name):
        keys = [k.decode() for k in self.iter(prefix='{}{}'.format(name, self.delimiter))]
        return keys
