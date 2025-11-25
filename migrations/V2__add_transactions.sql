CREATE TABLE transactions (
    id int PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    from_account_id int REFERENCES accounts (id),
    to_account_id int REFERENCES accounts (id),
    amount decimal(15, 2) NOT NULL,
    created_at timestamptz DEFAULT current_timestamp,
    CHECK (from_account_id IS NOT NULL OR to_account_id IS NOT NULL)
);
