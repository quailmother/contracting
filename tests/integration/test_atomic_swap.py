from unittest import TestCase
from contracting.db.driver import ContractDriver
from contracting.execution.executor import Executor
from contracting.stdlib.bridge.time import Datetime


def submission_kwargs_for_file(f):
    # Get the file name only by splitting off directories
    split = f.split('/')
    split = split[-1]

    # Now split off the .s
    split = split.split('.')
    contract_name = split[0]

    with open(f) as file:
        contract_code = file.read()

    return {
        'name': contract_name,
        'code': contract_code,
    }


TEST_SUBMISSION_KWARGS = {
    'sender': 'stu',
    'contract_name': 'submission',
    'function_name': 'submit_contract'
}


class TestAtomicSwapContract(TestCase):
    def setUp(self):
        self.d = ContractDriver()
        self.d.flush()

        with open('../../contracting/contracts/submission.s.py') as f:
            contract = f.read()

        self.d.set_contract(name='submission',
                            code=contract,
                            author='sys')
        self.d.commit()

        self.e = Executor(currency_contract='erc20_clone', metering=False)

        self.e.execute(**TEST_SUBMISSION_KWARGS,
                  kwargs=submission_kwargs_for_file('./test_contracts/erc20_clone.s.py'))

        self.e.execute(**TEST_SUBMISSION_KWARGS,
                  kwargs=submission_kwargs_for_file('./test_contracts/atomic_swaps.s.py'))

    def tearDown(self):
        ##self.d.flush()
        pass

    def test_initiate_not_enough_approved(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        status, res, stamps = self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5000000
        })

        self.assertEqual(status, 1)
        self.assertTrue(isinstance(res, AssertionError))

    def test_initiate_transfers_coins_correctly(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        _, atomic_swaps, _ = self.e.execute('stu', 'erc20_clone', 'balance_of', kwargs={'account':'atomic_swaps'})
        _, stu, _ = self.e.execute('stu', 'erc20_clone', 'balance_of', kwargs={'account': 'stu'})
        _, stu_as, _ = self.e.execute('stu', 'erc20_clone', 'allowance', kwargs={'owner': 'stu', 'spender': 'atomic_swaps'})

        self.assertEqual(atomic_swaps, 5)
        self.assertEqual(stu, 999995)
        self.assertEqual(stu_as, 999995)

    def test_initiate_writes_to_correct_key_and_properly(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        key = 'atomic_swaps.swaps:raghu:eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514'

        expiration, amount = self.d.get(key)
        self.assertEqual(expiration, Datetime(2020, 1, 1))
        self.assertEqual(amount, 5)

    def test_redeem_on_wrong_secret_fails(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        s, r, _ = self.e.execute('raghu', 'atomic_swaps', 'redeem', kwargs={'secret': '00'})

        self.assertEqual(s, 1)
        self.assertEqual(str(r), 'Incorrect sender or secret passed.')

    def test_redeem_on_wrong_sender_fails(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        s, r, _ = self.e.execute('stu', 'atomic_swaps', 'redeem', kwargs={'secret': '842b65a7d48e3a3c3f0e9d37eaced0b2'})

        self.assertEqual(s, 1)
        self.assertEqual(str(r), 'Incorrect sender or secret passed.')

    def test_past_expiration_fails(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        environment = {'now': Datetime(2021, 1, 1)}

        s, r, _ = self.e.execute('raghu', 'atomic_swaps', 'redeem', kwargs={'secret': '842b65a7d48e3a3c3f0e9d37eaced0b2'},
                              environment=environment)

        self.assertEqual(s, 1)
        self.assertEqual(str(r), 'Swap has expired.')

    def test_successful_redeem_transfers_coins_correctly(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        environment = {'now': Datetime(2019, 1, 1)}

        self.e.execute('raghu', 'atomic_swaps', 'redeem', kwargs={'secret': '842b65a7d48e3a3c3f0e9d37eaced0b2'},
                       environment=environment)

        _, atomic_swaps, _ = self.e.execute('stu', 'erc20_clone', 'balance_of', kwargs={'account': 'atomic_swaps'})
        _, raghu, _ = self.e.execute('stu', 'erc20_clone', 'balance_of', kwargs={'account': 'raghu'})

        self.assertEqual(raghu, 5)
        self.assertEqual(atomic_swaps, 0)

    def test_successful_redeem_deletes_entry(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        environment = {'now': Datetime(2019, 1, 1)}

        self.e.execute('raghu', 'atomic_swaps', 'redeem', kwargs={'secret': '842b65a7d48e3a3c3f0e9d37eaced0b2'},
                       environment=environment)

        key = 'atomic_swaps.swaps:raghu:eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514'
        v = self.d.get(key)

        self.assertEqual(v, None)

    def test_refund_works(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        environment = {'now': Datetime(2021, 1, 1)}

        self.e.execute('stu', 'atomic_swaps', 'refund', kwargs={'participant': 'raghu', 'secret': '842b65a7d48e3a3c3f0e9d37eaced0b2'},
                       environment=environment)

        _, atomic_swaps, _ = self.e.execute('stu', 'erc20_clone', 'balance_of', kwargs={'account': 'atomic_swaps'})
        _, stu, _ = self.e.execute('stu', 'erc20_clone', 'balance_of', kwargs={'account': 'stu'})

        self.assertEqual(stu, 1000000)
        self.assertEqual(atomic_swaps, 0)

    def test_refund_too_early_fails(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        environment = {'now': Datetime(2019, 1, 1)}

        _, res, _ = self.e.execute('stu', 'atomic_swaps', 'refund',
                       kwargs={'participant': 'raghu', 'secret': '842b65a7d48e3a3c3f0e9d37eaced0b2'},
                       environment=environment)

        self.assertEqual(str(res), 'Swap has not expired.')

    def test_refund_participant_is_signer_fails(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        environment = {'now': Datetime(2021, 1, 1)}

        _, res, _ = self.e.execute('raghu', 'atomic_swaps', 'refund',
                       kwargs={'participant': 'raghu', 'secret': '842b65a7d48e3a3c3f0e9d37eaced0b2'},
                       environment=environment)

        self.assertEqual(str(res), 'Caller and signer cannot issue a refund.')

    def test_refund_fails_with_wrong_secret(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        environment = {'now': Datetime(2019, 1, 1)}

        _, res, _ = self.e.execute('stu', 'atomic_swaps', 'refund',
                                kwargs={'participant': 'raghu', 'secret': '00'},
                                environment=environment)

        self.assertEqual(str(res), 'No swap to refund found.')

    def test_refund_resets_swaps(self):
        self.e.execute('stu', 'erc20_clone', 'approve', kwargs={'amount': 1000000, 'to': 'atomic_swaps'})
        self.e.execute('stu', 'atomic_swaps', 'initiate', kwargs={
            'participant': 'raghu',
            'expiration': Datetime(2020, 1, 1),
            'hashlock': 'eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514',
            'amount': 5
        })

        environment = {'now': Datetime(2021, 1, 1)}

        self.e.execute('stu', 'atomic_swaps', 'refund',
                       kwargs={'participant': 'raghu', 'secret': '842b65a7d48e3a3c3f0e9d37eaced0b2'},
                       environment=environment)

        key = 'atomic_swaps.swaps:raghu:eaf48a02d3a4bb3aeb0ecb337f6efb026ee0bbc460652510cff929de78935514'
        v = self.d.get(key)

        self.assertEqual(v, None)
