import os, threading
from multiprocessing import Lock
from seneca.parallelism.conflict_resolution import CRContext


# TODO rename this to just 'BookKeeper' if we decide we can cut out the global BookKeeper below
class BookKeeperInstance:
    def __init__(self, sbb_idx: int, contract_idx: int):
        assert sbb_idx >= 0, "sbb idx must be greater that or equal to 0"
        assert contract_idx >= 0, "contract idx must be greater that or equal to 0"
        self.sbb_idx, self.contract_idx = sbb_idx, contract_idx


class BookKeeper:
    _shared_state = {}
    _lock = Lock()

    @classmethod
    def _get_key(cls) -> str:
        """
        Returns a key unique to this particular thread/process combination.
        :return: The unique thead-process key (as a string)
        """
        key = "{}:{}".format(os.getpid(), threading.get_ident())
        return key

    @classmethod
    def _get_cr_key(cls) -> str:
        return cls._get_key() + ':CR'

    @classmethod
    def set_cr_info(cls, sbb_idx: int, contract_idx: int, data: CRContext, **kwargs) -> None:
        """
        Sets the info (subblock builder index and contract index) for the current thread.
        """
        key = cls._get_cr_key()
        with cls._lock:
            cls._shared_state[key] = {'sbb_idx': sbb_idx, 'contract_idx': contract_idx, 'data': data, **kwargs}

    @classmethod
    def get_cr_info(cls) -> dict:
        """
        Returns the info previously set for this specific thread by set_cr_info.
        :return:
        """
        key = cls._get_cr_key()
        with cls._lock:
            assert key in cls._shared_state, "Key {} not found in shared state. Did you call set_cr_info first?".format(key)
            return cls._shared_state[key]

    @classmethod
    def get_info(cls):
        key = cls._get_key()
        with cls._lock:
            assert key in cls._shared_state, "Key {} not found in shared state. Did you call set_info first?".format(key)
            return cls._shared_state[key]

    @classmethod
    def set_info(cls, **kwargs):
        key = cls._get_key()
        with cls._lock:
            cls._shared_state[key] = kwargs

    @classmethod
    def has_cr_info(cls) -> bool:
        """
        Checks if bookkeeping conflict resolution info exists for this current process/thread combination
        """
        key = cls._get_cr_key()
        with cls._lock:
            return key in cls._shared_state

    @classmethod
    def has_info(cls) -> bool:
        """
        Checks if bookkeeping info exists for this current process/thread combination
        """
        key = cls._get_key()
        with cls._lock:
            return key in cls._shared_state

    @classmethod
    def del_cr_info(cls) -> None:
        key = cls._get_cr_key()
        with cls._lock:
            assert key in cls._shared_state, "Key {} not found in shared state. Did you call set_cr_info first?"
            del cls._shared_state[key]

    @classmethod
    def del_info(cls) -> None:
        key = cls._get_key()
        with cls._lock:
            assert key in cls._shared_state, "Key {} not found in shared state. Did you call set_info first?"
            del cls._shared_state[key]

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._shared_state.clear()
