import importlib
import multiprocessing

from typing import Dict
import decimal

from . import runtime
from ..db.cr.transaction_bag import TransactionBag
from ..db.driver import ContractDriver, CacheDriver
from ..execution.module import install_database_loader, uninstall_builtins
from .. import config

STAMP_TO_TAU = 5000 # Manually set until voting added

class Executor:
    def __init__(self, production=False, driver=None, metering=True,
                 currency_contract='currency', balances_hash='balances'):

        self.metering = metering

        self.driver = driver
        if not self.driver:
            self.driver = ContractDriver()
        self.production = production

        if self.production:
            self.sandbox = MultiProcessingSandbox()
        else:
            self.sandbox = Sandbox()

        #self.metering = metering

        # Variables to tell Executor where to look for a balance to deduct for stamps if metering is enabled
        self.currency_contract = currency_contract
        self.balances_hash = balances_hash

        runtime.rt.env.update({'__Driver': self.driver})

    def execute_bag(self, bag: TransactionBag, environment={}, auto_commit=False, driver=None) -> Dict[int, tuple]:
        """
        The execute bag method sends a list of transactions to the sandbox to be executed
        In the case of bag execution the

        :param bag: a list of deserialized transaction objects
        :return: A dictionary with transaction index as the _key and execution result
                 objects as the value. Formatted as follows:

                 {
                    1: (0, 'balance=10')
                    2: (1, ImportError)
                 }
        """
        response_obj = {}

        for idx, tx in bag:
            response_obj[idx] = self.execute(tx.payload.sender, tx.contract_name, tx.func_name,
                                             tx.kwargs, stamps=tx.payload.stampsSupplied, auto_commit=auto_commit,
                                             environment=environment, driver=driver)
        return response_obj
        # results = self.sandbox.execute_bag(bag, environment=environment, auto_commit=auto_commit, driver=driver)
        # return results

    def execute(self, sender, contract_name, function_name, kwargs, environment={}, auto_commit=True, driver=None,
                stamps=1000000, metering=None) -> tuple:

        # Default to the self.metering property unless provided
        if metering is None:
            metering = self.metering

        runtime.rt.env.update({'__Driver': self.driver})

        if driver is None:
            driver = runtime.rt.env.get('__Driver')

        """
        Method that does a naive execute

        :param sender:
        :param contract_name:
        :param function_name:
        :param kwargs:
        :return: Dictionary containing the keys 'status_code' 'result' and 'error'
        """
        # A successful run is determined by if the sandbox execute command successfully runs.
        # Therefor we need to have a try catch to communicate success/fail back to the
        # client. Necessary in the case of batch run through bags where we still want to
        # continue execution in the case of failure of one of the transactions.
        balances_key = None
        if metering:

            balances_key = '{}{}{}{}{}'.format(self.currency_contract,
                                               config.INDEX_SEPARATOR,
                                               self.balances_hash,
                                               config.DELIMITER,
                                               sender)

            balance = driver.get(balances_key) or 0

            assert balance * STAMP_TO_TAU >= stamps, 'Sender does not have enough stamps for the transaction. \
                                       Balance at key {} is {}'.format(balances_key, balance)

        # Execute the function
        runtime.rt.set_up(stmps=stamps, meter=metering)
        status_code, result = self.sandbox.execute(sender, contract_name, function_name, kwargs,
                                                   auto_commit, environment, driver)
        runtime.rt.tracer.stop()

        # Deduct the stamps if that is enabled
        if metering:
            assert balances_key is not None, 'Balance key was not set properly. Cannot deduct stamps.'

            to_deduct = runtime.rt.tracer.get_stamp_used()
            to_deduct /= STAMP_TO_TAU

            to_deduct = decimal.Decimal(to_deduct)

            balance = driver.get(balances_key) or 0
            balance -= to_deduct

            driver.set(balances_key, balance)
            driver.commit()

        stamps_used = runtime.rt.tracer.get_stamp_used()
        runtime.rt.clean_up()
        runtime.rt.env.update({'__Driver': self.driver})

        return status_code, result, stamps_used


"""
The Sandbox class is used as a execution sandbox for a transaction.

I/O pattern:

    ------------                                  -----------
    | Executor |  ---> Transaction Bag (all) ---> | Sandbox |
    ------------                                  -----------
                                                       |
    ------------                                       v
    | Executor |  <---      Send Results     <---  Execute all tx
    ------------

    * The client sends the whole transaction bag to the Sandbox for
      processing. This is done to minimize back/forth I/O overhead
      and deadlocks
    * The sandbox executes all of the transactions one by one, resetting
      the syspath after each execution.
    * After all execution is complete, pass the full set of results
      back to the client again to minimize I/O overhead and deadlocks
    * Sandbox blocks on pipe again for new bag of transactions
"""


class Sandbox(object):
    def __init__(self):
        install_database_loader()

    def wipe_modules(self):
        uninstall_builtins()
        install_database_loader()

    def execute_bag(self, txbag, environment={}, auto_commit=False, driver=None):
        response_obj = {}

        for idx, tx in txbag:
            response_obj[idx] = self.execute(tx.payload.sender, tx.contract_name, tx.func_name,
                                             tx.kwargs, auto_commit=auto_commit,
                                             environment=environment, driver=driver)
        return response_obj

    def execute(self, sender, contract_name, function_name, kwargs, auto_commit=True,
                environment={}, driver=None):
        # Use _driver if one is provided, otherwise use the default _driver, ensuring to set it
        # back to default only if it was set previously to something else
        if driver:
            runtime.rt.env.update({'__Driver': driver})
        else:
            driver = runtime.rt.env.get('__Driver')

        # __main__ is replaced by the sender of the message in this case

        runtime.rt.ctx.clear()
        runtime.rt.ctx.append(sender)
        runtime.rt.env.update(environment)
        status_code = 0
        try:
            module = importlib.import_module(contract_name)
            #module = __import__(contract_name)

            func = getattr(module, function_name)

            result = func(**kwargs)

            if auto_commit:
                driver.commit()
        except Exception as e:
            print(str(e))
            result = e
            status_code = 1
            if auto_commit:
                driver.revert()
        finally:
            if isinstance(driver, CacheDriver):
                driver.new_tx()

        return status_code, result


# THIS SHOULD BE USED LATER
class MultiProcessingSandbox(Sandbox):
    def __init__(self):
        super().__init__()
        self.pipe = multiprocessing.Pipe()
        self.p = None

    def terminate(self):
        if self.p is not None:
            self.p.terminate()
        self.p = None

    def _lazy_instantiate(self):
        if self.p is None:
            self.p = multiprocessing.Process(target=self.process_loop,
                                             args=(super().execute, ))
            self.p.start()
            self.wipe_modules()

    def _update_driver_cache(self, driver, updated_driver):
        if updated_driver and isinstance(updated_driver, CacheDriver):
            driver.reset_cache(modified_keys=updated_driver.modified_keys,
                               contract_modifications=updated_driver.contract_modifications,
                               original_values=updated_driver.original_values)

    def execute_bag(self, txbag, environment={}, auto_commit=False, driver=None):
        self._lazy_instantiate()

        _, child_pipe = self.pipe

        msg = {
            '_driver': driver,
            'txns': {}
        }

        for tx_idx, tx in txbag:
            msg['txns'][tx_idx] = {
                'sender': tx.payload.sender,
                'contract_name': tx.contract_name,
                'function_name': tx.func_name,
                'kwargs': tx.kwargs,
                'auto_commit': auto_commit,
                'environment': environment
            }

        child_pipe.send(msg)

        response_obj = child_pipe.recv()
        self._update_driver_cache(driver, response_obj['_driver'])

        return response_obj['results']

    def execute(self, sender, contract_name, function_name, kwargs, auto_commit=True,
                environment={}, driver=None):
        self._lazy_instantiate()

        _, child_pipe = self.pipe

        # Sends code to be executed in the process loop
        # Create a message of type single execute
        # The reason it is a dictionary with a integer _key is
        # because we may be running a subset of the transactions but
        # still want to maintain order (e.g. 0,1,5)
        msg = {
            '_driver': driver,
            'txns': {
                0: {
                    'sender': sender,
                    'contract_name': contract_name,
                    'function_name': function_name,
                    'kwargs': kwargs,
                    'auto_commit': auto_commit,
                    'environment': environment
                }
            }
        }
        child_pipe.send(msg)

        # Receive result object back from process loop, formatted as
        # (status_code, result), loaded in using dill due to python
        # base pickler not knowning how to pickle module object
        # returned from execute
        response_obj = child_pipe.recv()
        self._update_driver_cache(driver, response_obj['_driver'])
        # In the case mp.execute() is called, we know we only have one
        # entry into the response object
        status_code, result = response_obj['results'][0]

        # Check the status code for failure, if failure raise the result
        return status_code, result

    def process_loop(self, execute_fn):
        parent_pipe, _ = self.pipe
        while True:
            msg = parent_pipe.recv()
            driver = msg['_driver']
            response_obj = {
                '_driver': driver,
                'results': {}
            }
            for tx_idx in sorted(msg['txns'].keys()):
                tx = msg['txns'][tx_idx]
                response_obj['results'][tx_idx] = execute_fn(tx['sender'], tx['contract_name'], tx['function_name'],
                                                             tx['kwargs'], auto_commit=tx['auto_commit'],
                                                             environment=tx['environment'], driver=driver)

            parent_pipe.send(response_obj)

