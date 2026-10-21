import json
import sqlite3
from pathlib import Path


class Journal:
    def __init__(self,path,plan_hash,code_hash):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self._lock=Path(str(path)+'.lock').open('a+b')
        self._lock.seek(0,2)
        if not self._lock.tell():self._lock.write(b'0');self._lock.flush()
        self._lock.seek(0)
        try:
            import os
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self._lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self._lock.close();raise ValueError('Journal já tem escritor ativo') from None
        try:self.db=sqlite3.connect(path,timeout=5)
        except Exception:
            self._lock.close();raise
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript("CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), plan TEXT, code TEXT); CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, snapshot TEXT NOT NULL, phase TEXT NOT NULL, reserved_cost REAL NOT NULL, result TEXT); CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
        row=self.db.execute('SELECT plan,code FROM metadata WHERE id=1').fetchone()
        if row and (row['plan']!=plan_hash or row['code']!=code_hash):
            self.close();raise ValueError('Sessão pertence a outro plano/código; não reiniciada')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO metadata VALUES(1,?,?)',(plan_hash,code_hash))
            self.db.execute("UPDATE requests SET phase='unknown' WHERE phase='pending'")
    def close(self):
        self.db.close()
        self._lock.close()
    def reserve(self,identity,snapshot,cost):
        if cost!=0 or isinstance(cost,bool):raise ValueError('Chamadas pagas proibidas no modo offline')
        encoded=json.dumps(snapshot,sort_keys=True,allow_nan=False)
        existing=self.request(identity)
        if existing and existing['snapshot']!=encoded:raise ValueError('Mesmo ID com estado diferente')
        with self.db:
            cursor=self.db.execute("INSERT OR IGNORE INTO requests(id,snapshot,phase,reserved_cost) VALUES(?,?,'pending',0)",(identity,encoded))
            return cursor.rowcount==1
    def request(self,identity):
        row=self.db.execute('SELECT * FROM requests WHERE id=?',(identity,)).fetchone()
        return dict(row) if row else None
    def finish(self,identity,result):
        with self.db:
            cursor=self.db.execute("UPDATE requests SET phase='completed',result=? WHERE id=? AND phase='pending'",(json.dumps(result,sort_keys=True,allow_nan=False),identity))
            if cursor.rowcount!=1:raise ValueError('Transição de request inválida')
    def get(self,key):
        row=self.db.execute('SELECT value FROM kv WHERE key=?',(key,)).fetchone()
        return json.loads(row['value']) if row else None
    def put(self,key,value):
        with self.db:self.db.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value,allow_nan=False)))

    def put_many(self,values):
        with self.db:
            for key,value in values.items():
                self.db.execute('INSERT INTO kv(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value,allow_nan=False)))
