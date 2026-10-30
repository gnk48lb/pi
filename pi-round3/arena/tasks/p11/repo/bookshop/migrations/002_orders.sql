CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books (id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_orders_book ON orders (book_id);
