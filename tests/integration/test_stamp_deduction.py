from unittest import TestCase
from contracting.db.driver import ContractDriver
from contracting.execution.executor import Executor


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


class TestMetering(TestCase):
    def setUp(self):
        # Hard load the submission contract
        self.d = ContractDriver()
        self.d.flush()

        with open('../../contracting/contracts/submission.s.py') as f:
            contract = f.read()

        self.d.set_contract(name='submission',
                            code=contract,
                            author='sys')
        self.d.commit()

        # Execute the currency contract with metering disabled
        self.e = Executor()
        self.e.execute(**TEST_SUBMISSION_KWARGS,
                       kwargs=submission_kwargs_for_file('./test_contracts/currency.s.py'), metering=False)

    def tearDown(self):
        # self.d.flush()
        pass

    def test_simple_execution_deducts_stamps(self):
        prior_balance = self.d.get('currency.balances:stu')

        status, result, stamps_used = self.e.execute('stu', 'currency', 'transfer', kwargs={'amount': 100, 'to': 'colin'})

        new_balance = self.d.get('currency.balances:stu')

        self.assertEqual(prior_balance - new_balance - 100, stamps_used)

    def test_too_few_stamps_fails_and_deducts_properly(self):
        prior_balance = self.d.get('currency.balances:stu')

        small_amount_of_stamps = 500

        status, result, stamps = self.e.execute('stu', 'currency', 'transfer', kwargs={'amount': 100, 'to': 'colin'},
                                                stamps=small_amount_of_stamps)

        new_balance = self.d.get('currency.balances:stu')

        self.assertEqual(prior_balance - new_balance, small_amount_of_stamps)

    def test_adding_too_many_stamps_throws_error(self):
        prior_balance = self.d.get('currency.balances:stu')

        too_many_stamps = prior_balance + 1000

        with self.assertRaises(AssertionError):
            status, result, stamps = self.e.execute('stu', 'currency', 'transfer', kwargs={'amount': 100, 'to': 'colin'},
                                                    stamps=too_many_stamps)

    def test_adding_all_stamps_with_infinate_loop_eats_all_balance(self):
        prior_balance = self.d.get('currency.balances:stu')

        self.e.execute(**TEST_SUBMISSION_KWARGS,
                        kwargs=submission_kwargs_for_file('./test_contracts/inf_loop.s.py'), stamps=prior_balance)

        new_balance = self.d.get('currency.balances:stu')

        self.assertEqual(new_balance, 0)

    def test_submitting_contract_succeeds_with_enough_stamps(self):
        prior_balance = self.d.get('currency.balances:stu')

        status, result, stamps = self.e.execute(**TEST_SUBMISSION_KWARGS,
                                                kwargs=submission_kwargs_for_file('./test_contracts/erc20_clone.s.py'),
                                                )

        new_balance = self.d.get('currency.balances:stu')

        self.assertEqual(prior_balance - new_balance, stamps)
