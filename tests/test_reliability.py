import sqlite3
from app.agent.reliability import LifecycleCoordinator, ReliabilityManager
def test_database_integrity_backup_and_doctor(tmp_path):
 db=tmp_path/'memory.db';sqlite3.connect(db).close();manager=ReliabilityManager(tmp_path);assert manager.database_check(db)['state']=='healthy';assert manager.backup_database(db,tmp_path/'backup')['verified'];assert manager.doctor({'memory':db})['success']
 assert LifecycleCoordinator(manager).startup({'memory':db})['success']; assert LifecycleCoordinator(manager).record_worker_crash('test', RuntimeError('boom'))['state']=='degraded'
