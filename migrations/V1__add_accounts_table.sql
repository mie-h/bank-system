CREATE TABLE users (
    id int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username text UNIQUE NOT NULL,
    created_at timestamptz DEFAULT current_timestamp

);

CREATE TABLE accounts (
    id int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id int REFERENCES users (id),
    balance decimal(15, 2) DEFAULT 0.00,
    created_at timestamptz DEFAULT current_timestamp
);
