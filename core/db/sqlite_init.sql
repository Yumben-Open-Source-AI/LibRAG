create table knowledge_base
(
    kb_name        VARCHAR not null,
    kb_description VARCHAR,
    keywords       VARCHAR,
    kb_id          INTEGER not null
        primary key,
    user_id        integer
        references user
);

create table document
(
    document_id          CHAR(32) not null
        primary key,
    document_name        VARCHAR  not null,
    document_description VARCHAR  not null,
    file_path            VARCHAR  not null,
    meta_data            JSON     not null,
    parse_strategy       VARCHAR  not null,
    kb_id                INTEGER
        references knowledge_base
);

create table domain
(
    domain_id          CHAR(32) not null
        primary key,
    domain_name        VARCHAR  not null,
    domain_description VARCHAR  not null,
    meta_data          JSON     not null,
    kb_id              INTEGER
        references knowledge_base
);

create table category
(
    category_id          CHAR(32) not null
        primary key,
    category_name        VARCHAR  not null,
    category_description VARCHAR  not null,
    meta_data            JSON     not null,
    parent_id            CHAR(32)
        references domain,
    kb_id                INTEGER
        references knowledge_base
);

create table category_document_link
(
    category_id CHAR(32) not null
        references category,
    document_id CHAR(32) not null
        references document,
    primary key (category_id, document_id)
);

create table paragraph
(
    paragraph_id       CHAR(32) not null
        primary key,
    paragraph_name     VARCHAR  not null,
    summary            VARCHAR  not null,
    content            TEXT,
    position           VARCHAR  not null,
    meta_data          JSON     not null,
    keywords           JSON     not null,
    parent_description VARCHAR  not null,
    parent_id          CHAR(32)
        references document,
    kb_id              INTEGER
        references knowledge_base
);

create table processing_task
(
    task_id        CHAR(32) not null
        primary key,
    file_path      VARCHAR  not null,
    parse_strategy VARCHAR  not null,
    status         VARCHAR  not null,
    created_at     DATETIME not null,
    started_at     DATETIME,
    completed_at   DATETIME,
    progress       INTEGER,
    kb_id          INTEGER
        references knowledge_base
);


create table user
(
    user_id         INTEGER not null
        primary key,
    email           VARCHAR not null,
    user_name       VARCHAR not null,
    full_name       VARCHAR not null,
    hashed_password VARCHAR not null,
    phone           VARCHAR,
    disabled        BOOLEAN,
    expire_time     DATETIME
);
INSERT INTO user (user_id, email, user_name, full_name, hashed_password, phone, disabled, expire_time) VALUES (1, '', 'admin', '', '$2b$12$tC.zimDt5QOZ9P982eQxKOLU4nJBk5OuYMAB.XBTmp/52fxe8/TTO', '', 0, null);
