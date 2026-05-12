#!/usr/bin/env python3
"""
Database Layer — PostgreSQL Integration
========================================
Production-grade database for Minervini Trading System
"""

import psycopg2
from psycopg2 import pool
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict

# ===== Logging =====
logging.basicConfig(level=logging.INFO, format='[DB] %(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ===== Config =====
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "minervini_db",
    "user":     "minervini",
    "password": "minervini123",
}

# ===== Connection Pool =====
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=10, **DB_CONFIG
            )
            logger.info("Connection pool created")
        except Exception as e:
            logger.error(f"Pool creation failed: {e}")
            raise
    return _pool

def get_conn():
    return get_pool().getconn()

def put_conn(conn):
    get_pool().putconn(conn)

# ===========================================================
# INIT DATABASE — Create Tables
# ===========================================================
def init_database():
    conn = get_conn()
    try:
        cur = conn.cursor()

        # trade_logs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_logs (
                id              SERIAL PRIMARY KEY,
                symbol          VARCHAR(10) NOT NULL,
                timestamp       TIMESTAMP DEFAULT NOW(),
                score           FLOAT,
                rating          VARCHAR(10),
                decision        VARCHAR(20),
                entry_price     FLOAT,
                stop_loss       FLOAT,
                target_1        FLOAT,
                target_2        FLOAT,
                position_size   INT,
                market_regime   VARCHAR(20),
                volume_ratio    FLOAT,
                orb_signal      BOOLEAN,
                mtf_alignment   BOOLEAN,
                status          VARCHAR(20) DEFAULT 'OPEN'
            );
        """)

        # rejection_logs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rejection_logs (
                id              SERIAL PRIMARY KEY,
                symbol          VARCHAR(10) NOT NULL,
                timestamp       TIMESTAMP DEFAULT NOW(),
                reason          TEXT,
                score           FLOAT,
                warnings        TEXT,
                market_regime   VARCHAR(20)
            );
        """)

        # market_snapshots
        cur.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id              SERIAL PRIMARY KEY,
                timestamp       TIMESTAMP DEFAULT NOW(),
                spy             FLOAT,
                vix             FLOAT,
                dxy             FLOAT,
                market_regime   VARCHAR(20),
                breadth         FLOAT,
                risk_on         BOOLEAN
            );
        """)

        conn.commit()
        logger.info("✅ Tables initialized successfully")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"init_database error: {e}")
        return False
    finally:
        cur.close()
        put_conn(conn)

# ===========================================================
# INSERT FUNCTIONS
# ===========================================================
def insert_trade_log(data: dict) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO trade_logs
            (symbol, score, rating, decision, entry_price, stop_loss,
             target_1, target_2, position_size, market_regime,
             volume_ratio, orb_signal, mtf_alignment, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get("symbol"),
            data.get("score"),
            data.get("rating"),
            data.get("decision", "SCAN"),
            data.get("entry_price") or data.get("current_price"),
            data.get("stop_loss"),
            data.get("target_1"),
            data.get("target_2"),
            data.get("position_size"),
            data.get("market_regime"),
            data.get("volume_ratio") or data.get("rv"),
            data.get("orb_breakout", False),
            data.get("mtf_alignment", False),
            data.get("status", "SCAN"),
        ))
        conn.commit()
        logger.info(f"Trade log inserted: {data.get('symbol')} {data.get('rating')}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"insert_trade_log error: {e}")
        return False
    finally:
        cur.close()
        put_conn(conn)

def insert_rejection_log(data: dict) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        warnings = json.dumps(data.get("warnings", []))
        cur.execute("""
            INSERT INTO rejection_logs
            (symbol, reason, score, warnings, market_regime)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            data.get("symbol"),
            data.get("reason") or data.get("blocks", [""])[0] if data.get("blocks") else "",
            data.get("score"),
            warnings,
            data.get("market_regime", "UNKNOWN"),
        ))
        conn.commit()
        logger.info(f"Rejection log inserted: {data.get('symbol')}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"insert_rejection_log error: {e}")
        return False
    finally:
        cur.close()
        put_conn(conn)

def insert_market_snapshot(data: dict) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO market_snapshots
            (spy, vix, dxy, market_regime, breadth, risk_on)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            data.get("spy"),
            data.get("vix"),
            data.get("dxy"),
            data.get("market_regime", "NEUTRAL"),
            data.get("breadth"),
            data.get("risk_on", False),
        ))
        conn.commit()
        logger.info("Market snapshot inserted")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"insert_market_snapshot error: {e}")
        return False
    finally:
        cur.close()
        put_conn(conn)

# ===========================================================
# FETCH FUNCTIONS
# ===========================================================
def fetch_recent_trades(limit: int = 20) -> List[Dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, symbol, timestamp, score, rating, decision,
                   entry_price, stop_loss, target_1, market_regime, status
            FROM trade_logs
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return rows
    except Exception as e:
        logger.error(f"fetch_recent_trades error: {e}")
        return []
    finally:
        cur.close()
        put_conn(conn)

def fetch_recent_rejections(limit: int = 20) -> List[Dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, symbol, timestamp, reason, score, market_regime
            FROM rejection_logs
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return rows
    except Exception as e:
        logger.error(f"fetch_recent_rejections error: {e}")
        return []
    finally:
        cur.close()
        put_conn(conn)

def fetch_recent_snapshots(limit: int = 10) -> List[Dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, timestamp, spy, vix, market_regime, risk_on
            FROM market_snapshots
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return rows
    except Exception as e:
        logger.error(f"fetch_recent_snapshots error: {e}")
        return []
    finally:
        cur.close()
        put_conn(conn)

def get_stats() -> Dict:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM trade_logs")
        total_trades = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM rejection_logs")
        total_rejections = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM market_snapshots")
        total_snapshots = cur.fetchone()[0]
        return {
            "total_trades":     total_trades,
            "total_rejections": total_rejections,
            "total_snapshots":  total_snapshots,
        }
    except Exception as e:
        logger.error(f"get_stats error: {e}")
        return {}
    finally:
        cur.close()
        put_conn(conn)

if __name__ == "__main__":
    print("[DB] Initializing database...")
    init_database()
    print("[DB] ✅ Done")
