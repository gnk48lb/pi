ALTER TABLE books ADD COLUMN deleted_at TEXT;

DROP INDEX idx_books_isbn;
CREATE UNIQUE INDEX idx_books_isbn_live ON books (isbn) WHERE deleted_at IS NULL;
