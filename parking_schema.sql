-- DBTYPE=MYSQL
DROP TABLE IF EXISTS T_ACCOUNT_CONSUME;
DROP TABLE IF EXISTS T_ACCOUNT_RECEIPT;
DROP TABLE IF EXISTS T_ACCOUNT;
DROP TABLE IF EXISTS T_PAYMENT;
DROP TABLE IF EXISTS T_ORDER;
DROP TABLE IF EXISTS T_PRODUCT;

CREATE TABLE T_PRODUCT (
    ID BIGINT NOT NULL AUTO_INCREMENT,
    NAME VARCHAR(100) NOT NULL,
    DISPLAY_NAME VARCHAR(200) NOT NULL,
    PLACES_AVAIL INT NOT NULL,
    PRICE DECIMAL(16, 6) NOT NULL
    , PRIMARY KEY (ID)
) ENGINE=INNODB DEFAULT CHARSET=utf8;

CREATE TABLE T_ORDER (
    ID BIGINT NOT NULL AUTO_INCREMENT,
    PRODUCT_ID BIGINT NOT NULL,
    USER_EID VARCHAR(100) NULL,
    TICKET_NUMBER VARCHAR(100) NULL,
    PLATE_NUMBER VARCHAR(20) NULL,
    START_TS TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PAID_UNTIL_TS TIMESTAMP NOT NULL,
    FINISH_TS TIMESTAMP NULL,
    PAID_AMOUNT DECIMAL(16, 6) NOT NULL,
    PRICE DECIMAL(16, 6) NULL
    , PRIMARY KEY (ID)
) ENGINE=INNODB DEFAULT CHARSET=utf8;

CREATE TABLE T_PAYMENT (
    ID BIGINT NOT NULL AUTO_INCREMENT,
    TRANS_NUMBER VARCHAR(100) NOT NULL,
    ORDER_ID BIGINT NOT NULL,
    TS TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    HOURS DECIMAL(16, 6) NOT NULL,
    AMOUNT DECIMAL(16, 6) NOT NULL,
    PAYMENT_TS TIMESTAMP NULL,
    CANCEL_TS TIMESTAMP NULL
    , PRIMARY KEY (ID)
) ENGINE=INNODB DEFAULT CHARSET=utf8;

CREATE TABLE T_ACCOUNT (
    ID BIGINT NOT NULL AUTO_INCREMENT,
    USER_EID VARCHAR(100) NOT NULL,
    BALANCE DECIMAL(16, 6) NOT NULL,
    RESERVED DECIMAL(16, 6) NOT NULL
    , PRIMARY KEY (ID)
) ENGINE=INNODB DEFAULT CHARSET=utf8;

CREATE TABLE T_ACCOUNT_RECEIPT (
    ID BIGINT NOT NULL AUTO_INCREMENT,
    TS TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ACCOUNT_ID BIGINT NOT NULL,
    SRC_ORDER_ID BIGINT NOT NULL,
    AMOUNT DECIMAL(16, 6) NOT NULL
    , PRIMARY KEY (ID)
) ENGINE=INNODB DEFAULT CHARSET=utf8;

CREATE TABLE T_ACCOUNT_CONSUME (
    ID BIGINT NOT NULL AUTO_INCREMENT,
    TS TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ACCOUNT_ID BIGINT NOT NULL,
    DST_PAYMENT_ID BIGINT NOT NULL,
    AMOUNT DECIMAL(16, 6) NOT NULL,
    IS_RESERVED INT NOT NULL
    , PRIMARY KEY (ID)
) ENGINE=INNODB DEFAULT CHARSET=utf8;

CREATE TABLE T_ACCOUNT_TRANSFER (
    ID BIGINT NOT NULL AUTO_INCREMENT,
    TS TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    TRANS_NUMBER VARCHAR(100) NOT NULL,
    SRC_ACCOUNT_ID BIGINT NOT NULL,
    DST_ACCOUNT_ID BIGINT NOT NULL,
    AMOUNT DECIMAL(16, 6) NOT NULL
    , PRIMARY KEY (ID)
) ENGINE=INNODB DEFAULT CHARSET=utf8;

ALTER TABLE T_ORDER ADD FOREIGN KEY (PRODUCT_ID) REFERENCES T_PRODUCT(ID);

ALTER TABLE T_PAYMENT ADD FOREIGN KEY (ORDER_ID) REFERENCES T_ORDER(ID);

ALTER TABLE T_ACCOUNT_RECEIPT ADD FOREIGN KEY (ACCOUNT_ID)
    REFERENCES T_ACCOUNT(ID);

ALTER TABLE T_ACCOUNT_RECEIPT ADD FOREIGN KEY (SRC_ORDER_ID)
    REFERENCES T_ORDER(ID);

ALTER TABLE T_ACCOUNT_CONSUME ADD FOREIGN KEY (ACCOUNT_ID)
    REFERENCES T_ACCOUNT(ID);

ALTER TABLE T_ACCOUNT_CONSUME ADD FOREIGN KEY (DST_PAYMENT_ID)
    REFERENCES T_PAYMENT(ID);

ALTER TABLE T_ACCOUNT_TRANSFER ADD FOREIGN KEY (SRC_ACCOUNT_ID)
    REFERENCES T_ACCOUNT(ID);

ALTER TABLE T_ACCOUNT_TRANSFER ADD FOREIGN KEY (DST_ACCOUNT_ID)
    REFERENCES T_ACCOUNT(ID);

CREATE UNIQUE INDEX I_PRODUCT_NAME ON T_PRODUCT(NAME);

CREATE UNIQUE INDEX I_ORDER_PARK_NUM ON T_ORDER(PRODUCT_ID, TICKET_NUMBER);
CREATE INDEX I_ORDER_PLATE_NUMBER ON T_ORDER(PLATE_NUMBER);
CREATE INDEX I_ORDER_USER_EID ON T_ORDER(USER_EID);
CREATE INDEX I_ORDER_PAID_UNTIL ON T_ORDER(PAID_UNTIL_TS);

CREATE UNIQUE INDEX I_PAYMENT_NUMBER ON T_PAYMENT(TRANS_NUMBER);

CREATE UNIQUE INDEX I_ACCOUNT_USER_EID ON T_ACCOUNT(USER_EID);

CREATE INDEX I_ACC_RECEIPT_ACC_ID ON T_ACCOUNT_RECEIPT(ACCOUNT_ID);
CREATE INDEX I_ACC_RECEIPT_ORDER_ID ON T_ACCOUNT_RECEIPT(SRC_ORDER_ID);

CREATE INDEX I_ACC_CONSUME_ACC_ID ON T_ACCOUNT_CONSUME(ACCOUNT_ID);
CREATE INDEX I_ACC_CONSUME_PAYMENT_ID ON T_ACCOUNT_CONSUME(DST_PAYMENT_ID);

CREATE UNIQUE INDEX I_ACCOUNT_TRANS_NUM ON T_PAYMENT(TRANS_NUMBER);

INSERT INTO T_PRODUCT(NAME, DISPLAY_NAME, PLACES_AVAIL, PRICE) VALUES ('1333', 'N1333', 8000, 51);
INSERT INTO T_PRODUCT(NAME, DISPLAY_NAME, PLACES_AVAIL, PRICE) VALUES ('15001', 'N15001', 5000, 60);

COMMIT;

