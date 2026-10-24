"""Bounded public-data threads; timed-out jobs are not submitted again.

Future timeout is a reporting deadline, not thread cancellation. Each worker
owns a client with a transport timeout; close waits for outstanding IO.
"""
from concurrent.futures import ThreadPoolExecutor, wait
import threading
import time
from spot_engine.data import PublicBinance, download, retry


class CollectionError(ValueError): pass


def public_factory(timeout_s):
    client=PublicBinance()
    client._exchange.timeout=int(timeout_s*1000)
    return client


class ParallelCollector:
    def __init__(self, symbols, max_workers=4, client_factory=public_factory):
        if type(max_workers) is not int or not 1<=max_workers<=6:
            raise ValueError('MAX_WORKERS_1_TO_6')
        if not symbols or len(set(symbols))!=len(symbols):raise ValueError('INVALID_SYMBOLS')
        self.symbols=tuple(symbols);self.factory=client_factory
        self.pool=ThreadPoolExecutor(max_workers=max_workers,thread_name_prefix='v3-public')
        self.local=threading.local();self.inflight={};self.closed=False;self.timings={}

    def _client(self, timeout):
        # Never share a rate-limiter/session object across threads.
        if not hasattr(self.local,'client') or self.local.timeout!=timeout:
            self.local.client=self.factory(timeout);self.local.timeout=timeout
        return self.local.client

    def _batch(self, kind, operation, timeout_s):
        if self.closed:raise CollectionError('COLLECTOR_CLOSED')
        if not isinstance(timeout_s,(int,float)) or not 0<timeout_s<=900:
            raise CollectionError('INVALID_TIMEOUT')
        jobs={}; results={}
        def task(symbol):
            start=time.monotonic()
            try:return operation(self._client(min(timeout_s,15)),symbol)
            finally:self.timings[symbol]=(time.monotonic()-start)*1000
        # At most one outstanding request per symbol, including other batch types.
        for symbol in self.symbols:
            previous=self.inflight.get(symbol)
            if previous and not previous.done():
                results[symbol]=CollectionError('PREVIOUS_REQUEST_STILL_RUNNING');continue
            future=self.pool.submit(task,symbol);jobs[symbol]=future;self.inflight[symbol]=future
        _,pending=wait(jobs.values(),timeout=timeout_s) if jobs else (set(),set())
        for symbol,future in jobs.items():
            if future in pending:results[symbol]=CollectionError('PUBLIC_DATA_TIMEOUT')
            else:
                try:results[symbol]=future.result()
                except Exception:results[symbol]=CollectionError('PUBLIC_DATA_UNAVAILABLE')
        return results

    def fetch_books(self, timeout_s=3.):
        return self._batch('book',lambda c,s:retry(lambda:c.fetch_book(s)),timeout_s)

    def fetch_candles_batch(self,timeframe,since_ms,until_ms,timeout_s=300.):
        return self._batch('candles',lambda c,s:download(c,s,timeframe,since_ms,until_ms),timeout_s)

    def close(self):
        self.closed=True;self.pool.shutdown(wait=True)
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
