"""SQLite schema creation for the Finance PnL application."""

from __future__ import annotations

import sqlite3


def create_schema(connection: sqlite3.Connection) -> None:
    """Create all tables and indexes required by the MVP."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            value_date TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            counterparty TEXT NOT NULL,
            currency_buy TEXT NOT NULL,
            amount_buy REAL NOT NULL,
            currency_sell TEXT NOT NULL,
            amount_sell REAL NOT NULL,
            rate_fact REAL NOT NULL,
            commission REAL NOT NULL DEFAULT 0,
            portfolio TEXT NOT NULL,
            comment TEXT,
            external_deal_id TEXT,
            manager TEXT,
            is_repeat_payment INTEGER,
            repeat_payment_commission_percent REAL,
            repeat_payment_penalty_usd REAL,
            request_date TEXT,
            client_fix_date TEXT,
            agent_writeoff_date TEXT,
            client_receive_date TEXT,
            is_refund INTEGER,
            agent_refund_date TEXT,
            client_refund_date TEXT,
            payment_status TEXT,
            client_name TEXT,
            review_status TEXT,
            receiver_company TEXT,
            receiver_bank_country TEXT,
            deal_amount REAL,
            deal_currency TEXT,
            client_rate_percent REAL,
            fixed_commission_amount REAL,
            fixed_commission_currency TEXT,
            swift_amount REAL,
            swift_currency TEXT,
            client_fix_rate REAL,
            usd_rate REAL,
            client_cross_rate REAL,
            payment_agent TEXT,
            agent_commission_amount REAL,
            agent_commission_currency TEXT,
            swift_commission_amount REAL,
            swift_commission_currency TEXT,
            customer_article_name TEXT,
            pnl_client_percent_fee_usd REAL,
            pnl_fixed_commission_usd REAL,
            pnl_swift_usd REAL,
            pnl_agent_commission_usd REAL,
            pnl_swift_commission_usd REAL,
            pnl_referral_commission_usd REAL,
            source_file TEXT,
            source_sheet TEXT,
            source_row_number INTEGER,
            import_batch_id INTEGER,
            raw_payload_json TEXT,
            included_in_calc INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(import_batch_id) REFERENCES import_batches(id)
        );

        CREATE INDEX IF NOT EXISTS idx_deals_trade_date ON deals(trade_date);
        CREATE INDEX IF NOT EXISTS idx_deals_portfolio ON deals(portfolio);
        CREATE INDEX IF NOT EXISTS idx_deals_currencies
            ON deals(currency_buy, currency_sell);

        CREATE TABLE IF NOT EXISTS import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            source_sheet TEXT NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            rows_total INTEGER NOT NULL DEFAULT 0,
            rows_success INTEGER NOT NULL DEFAULT 0,
            rows_failed INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            error_message TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_import_batches_imported_at
            ON import_batches(imported_at);

        CREATE TABLE IF NOT EXISTS import_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_batch_id INTEGER NOT NULL,
            source_row_number INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            error_message TEXT NOT NULL,
            raw_value TEXT,
            raw_payload_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(import_batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_import_errors_batch
            ON import_errors(import_batch_id);

        CREATE TABLE IF NOT EXISTS rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rate_date TEXT NOT NULL,
            currency TEXT NOT NULL,
            rate_to_rub REAL NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(rate_date, currency, source)
        );

        CREATE INDEX IF NOT EXISTS idx_rates_lookup
            ON rates(rate_date, currency, source);

        CREATE TABLE IF NOT EXISTS rate_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_set_name TEXT NOT NULL DEFAULT 'default',
            order_index INTEGER NOT NULL,
            bank_name TEXT NOT NULL,
            currency TEXT NOT NULL,
            min_amount REAL NOT NULL,
            max_amount REAL,
            region TEXT,
            start_date TEXT,
            end_date TEXT,
            rate REAL NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            source_file TEXT,
            source_sheet TEXT,
            source_row_number INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            description TEXT,
            logo_path TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS referral_sync_ignored (
            name_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS rate_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referral_id INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 100,
            operation_type TEXT,
            currency TEXT,
            amount_from REAL,
            amount_to REAL,
            amount_basis TEXT NOT NULL DEFAULT 'deal_currency',
            region TEXT,
            date_from TEXT,
            date_to TEXT,
            rate_value REAL NOT NULL,
            percent_commission_currency TEXT,
            fixed_commission_amount REAL,
            fixed_commission_currency TEXT,
            commission_type TEXT NOT NULL DEFAULT 'percent',
            comment TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(referral_id) REFERENCES referrals(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(code);
        CREATE INDEX IF NOT EXISTS idx_referrals_name ON referrals(name);
        CREATE INDEX IF NOT EXISTS idx_rate_conditions_referral
            ON rate_conditions(referral_id, is_active, priority);
        CREATE INDEX IF NOT EXISTS idx_rate_conditions_lookup
            ON rate_conditions(referral_id, is_active, currency, region);

        CREATE TABLE IF NOT EXISTS client_rate_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL UNIQUE,
            note TEXT NOT NULL,
            date_from TEXT NOT NULL,
            date_to TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_client_rate_exceptions_client
            ON client_rate_exceptions(client_name, date_from, date_to);

        """
    )
    _ensure_deals_import_columns(connection)
    _ensure_rate_rules_schema(connection)
    _ensure_referral_rate_schema(connection)
    _ensure_client_rate_exceptions_schema(connection)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_deals_import_batch ON deals(import_batch_id)"
    )
    connection.commit()


def _ensure_deals_import_columns(connection: sqlite3.Connection) -> None:
    """Add import metadata columns when upgrading an existing local database."""
    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(deals)").fetchall()
    }
    columns = {
        "source_sheet": "TEXT",
        "source_row_number": "INTEGER",
        "import_batch_id": "INTEGER",
        "raw_payload_json": "TEXT",
        "external_deal_id": "TEXT",
        "manager": "TEXT",
        "is_repeat_payment": "INTEGER",
        "repeat_payment_commission_percent": "REAL",
        "repeat_payment_penalty_usd": "REAL",
        "request_date": "TEXT",
        "client_fix_date": "TEXT",
        "agent_writeoff_date": "TEXT",
        "client_receive_date": "TEXT",
        "is_refund": "INTEGER",
        "agent_refund_date": "TEXT",
        "client_refund_date": "TEXT",
        "payment_status": "TEXT",
        "client_name": "TEXT",
        "review_status": "TEXT",
        "receiver_company": "TEXT",
        "receiver_bank_country": "TEXT",
        "deal_amount": "REAL",
        "deal_currency": "TEXT",
        "client_rate_percent": "REAL",
        "fixed_commission_amount": "REAL",
        "fixed_commission_currency": "TEXT",
        "swift_amount": "REAL",
        "swift_currency": "TEXT",
        "client_fix_rate": "REAL",
        "usd_rate": "REAL",
        "client_cross_rate": "REAL",
        "payment_agent": "TEXT",
        "agent_commission_amount": "REAL",
        "agent_commission_currency": "TEXT",
        "swift_commission_amount": "REAL",
        "swift_commission_currency": "TEXT",
        "customer_article_name": "TEXT",
        "pnl_client_percent_fee_usd": "REAL",
        "pnl_fixed_commission_usd": "REAL",
        "pnl_swift_usd": "REAL",
        "pnl_agent_commission_usd": "REAL",
        "pnl_swift_commission_usd": "REAL",
        "pnl_referral_commission_usd": "REAL",
    }
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE deals ADD COLUMN {column_name} {column_type}")
    connection.execute("UPDATE deals SET is_repeat_payment = 0 WHERE is_repeat_payment IS NULL")
    connection.execute("UPDATE deals SET is_refund = 0 WHERE is_refund IS NULL")


def _ensure_rate_rules_schema(connection: sqlite3.Connection) -> None:
    """Ensure rate_rules uses the rules-engine schema, preserving legacy table."""
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'rate_rules'"
    ).fetchone()
    if not table_exists:
        _create_rate_rules_table(connection)
        return

    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(rate_rules)").fetchall()
    }
    required_columns = {
        "rule_set_name",
        "order_index",
        "bank_name",
        "currency",
        "min_amount",
        "max_amount",
        "region",
        "start_date",
        "end_date",
        "rate",
        "is_active",
        "source_file",
        "source_sheet",
        "source_row_number",
        "created_at",
        "updated_at",
    }
    if required_columns.issubset(existing_columns):
        return

    legacy_name = _next_legacy_table_name(connection, "rate_rules_legacy")
    connection.execute(f"ALTER TABLE rate_rules RENAME TO {legacy_name}")
    _create_rate_rules_table(connection)


def _create_rate_rules_table(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS rate_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_set_name TEXT NOT NULL DEFAULT 'default',
            order_index INTEGER NOT NULL,
            bank_name TEXT NOT NULL,
            currency TEXT NOT NULL,
            min_amount REAL NOT NULL,
            max_amount REAL,
            region TEXT,
            start_date TEXT,
            end_date TEXT,
            rate REAL NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            source_file TEXT,
            source_sheet TEXT,
            source_row_number INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_rate_rules_engine_lookup
            ON rate_rules(is_active, rule_set_name, order_index, bank_name, currency);
        """
    )


def _ensure_referral_rate_schema(connection: sqlite3.Connection) -> None:
    """Create referral-based rate tables when upgrading an existing database."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            description TEXT,
            logo_path TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS referral_sync_ignored (
            name_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS rate_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referral_id INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 100,
            operation_type TEXT,
            currency TEXT,
            amount_from REAL,
            amount_to REAL,
            amount_basis TEXT NOT NULL DEFAULT 'deal_currency',
            region TEXT,
            date_from TEXT,
            date_to TEXT,
            rate_value REAL NOT NULL,
            percent_commission_currency TEXT,
            fixed_commission_amount REAL,
            fixed_commission_currency TEXT,
            commission_type TEXT NOT NULL DEFAULT 'percent',
            comment TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(referral_id) REFERENCES referrals(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(code);
        CREATE INDEX IF NOT EXISTS idx_referrals_name ON referrals(name);
        CREATE INDEX IF NOT EXISTS idx_rate_conditions_referral
            ON rate_conditions(referral_id, is_active, priority);
        CREATE INDEX IF NOT EXISTS idx_rate_conditions_lookup
            ON rate_conditions(referral_id, is_active, currency, region);
        """
    )
    existing_columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(rate_conditions)").fetchall()
    }
    if "amount_basis" not in existing_columns:
        connection.execute(
            "ALTER TABLE rate_conditions ADD COLUMN amount_basis TEXT NOT NULL DEFAULT 'deal_currency'"
        )
    if "operation_type" not in existing_columns:
        connection.execute("ALTER TABLE rate_conditions ADD COLUMN operation_type TEXT")
    if "percent_commission_currency" not in existing_columns:
        connection.execute("ALTER TABLE rate_conditions ADD COLUMN percent_commission_currency TEXT")
    if "fixed_commission_amount" not in existing_columns:
        connection.execute("ALTER TABLE rate_conditions ADD COLUMN fixed_commission_amount REAL")
    if "fixed_commission_currency" not in existing_columns:
        connection.execute("ALTER TABLE rate_conditions ADD COLUMN fixed_commission_currency TEXT")
    connection.execute(
        """
        UPDATE rate_conditions
        SET fixed_commission_amount = rate_value,
            rate_value = 0,
            commission_type = 'mixed'
        WHERE commission_type = 'fixed'
          AND fixed_commission_amount IS NULL
        """
    )
    connection.execute(
        """
        UPDATE rate_conditions
        SET commission_type = 'mixed'
        WHERE commission_type IN ('percent', 'fixed')
        """
    )


def _ensure_client_rate_exceptions_schema(connection: sqlite3.Connection) -> None:
    """Create client exception table for manual referral commission rules."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS client_rate_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL UNIQUE,
            note TEXT NOT NULL,
            date_from TEXT NOT NULL,
            date_to TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_client_rate_exceptions_client
            ON client_rate_exceptions(client_name, date_from, date_to);
        """
    )
    _relax_client_rate_exceptions_date_to(connection)


def _relax_client_rate_exceptions_date_to(connection: sqlite3.Connection) -> None:
    """Allow empty date_to for perpetual client exceptions in upgraded databases."""
    table_info = connection.execute("PRAGMA table_info(client_rate_exceptions)").fetchall()
    date_to = next((row for row in table_info if row["name"] == "date_to"), None)
    if date_to is None or int(date_to["notnull"]) == 0:
        return
    connection.executescript(
        """
        ALTER TABLE client_rate_exceptions RENAME TO client_rate_exceptions_legacy_notnull;

        CREATE TABLE client_rate_exceptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL UNIQUE,
            note TEXT NOT NULL,
            date_from TEXT NOT NULL,
            date_to TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO client_rate_exceptions (
            id, client_name, note, date_from, date_to, created_at, updated_at
        )
        SELECT id, client_name, note, date_from, date_to, created_at, updated_at
        FROM client_rate_exceptions_legacy_notnull;

        DROP TABLE client_rate_exceptions_legacy_notnull;

        CREATE INDEX IF NOT EXISTS idx_client_rate_exceptions_client
            ON client_rate_exceptions(client_name, date_from, date_to);
        """
    )


def _next_legacy_table_name(connection: sqlite3.Connection, base_name: str) -> str:
    index = 1
    while True:
        candidate = f"{base_name}_{index}"
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (candidate,),
        ).fetchone()
        if not exists:
            return candidate
        index += 1
